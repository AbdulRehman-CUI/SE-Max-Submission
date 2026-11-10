import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import Mock
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import column, table
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.routes.budgets import get_budget_service, router
from backend.app.schemas import BudgetCreate, BudgetResponse, BudgetSummary, BudgetUpdate
from backend.app.services.budget_service import BudgetPeriodChangeError, BudgetService, DuplicateBudgetError

USER_ID = uuid4()
BUDGET_ID = uuid4()
BUDGET_PATH = f"/budgets/{BUDGET_ID}"
BUDGET_BODY = {"category": "Groceries", "budget_limit": "10000.00", "month": 12, "year": 2026}
AUTH = {"Authorization": "Bearer test-user"}
ROW = {
    **BUDGET_BODY,
    "id": BUDGET_ID,
    "user_id": USER_ID,
    "created_at": datetime(2026, 12, 1, tzinfo=timezone.utc),
    "budget_limit": Decimal("10000.00"),
    "total_spent": Decimal("12000.25"),
    "remaining_budget": Decimal("-2000.25"),
}


class _ModelStub:
    """SQL expression columns and a plain row factory for mocked sessions."""

    def __init__(self, name, columns):
        self.table = table(name, *(column(name) for name in columns.split()))
        for item in self.table.c:
            setattr(self, item.name, item)

    def __clause_element__(self):
        return self.table

    def __call__(self, **values):
        return SimpleNamespace(id=BUDGET_ID, **values)


_BUDGET = _ModelStub("budgets", "id user_id created_at category budget_limit month year")
_EXPENSE = _ModelStub("expenses", "user_id category currency transaction_date amount")


def _compile(statement):
    query = statement.compile(dialect=postgresql.dialect())
    return str(query), query.params


class BudgetServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock(spec=Session)
        self.db.scalar.return_value = False
        self.query_result = self.db.execute.return_value
        self.rows = self.query_result.mappings.return_value
        self.rows.one.return_value = ROW
        self.rows.one_or_none.return_value = ROW
        self.service = BudgetService(self.db, USER_ID, _BUDGET, _EXPENSE)

    def test_create_checks_uniqueness_before_inserting_as_authenticated_user(self):
        response = self.service.create_budget(BudgetCreate.model_validate(BUDGET_BODY))
        stored = self.db.add.call_args.args[0]
        self.assertEqual(stored.user_id, USER_ID)
        self.assertIsInstance(stored.budget_limit, Decimal)
        self.assertEqual(stored.budget_limit, Decimal("10000.00"))
        self.assertEqual(response.remaining_budget, Decimal("-2000.25"))
        self.assertEqual(
            [call[0] for call in self.db.method_calls[:3]], ["scalar", "add", "flush"]
        )
        sql, params = _compile(self.db.scalar.call_args.args[0])
        self.assertIn("EXISTS", sql)
        self.assertEqual(
            set(params.values()), {USER_ID, "Groceries", 12, 2026}
        )
        self.db.commit.assert_called_once_with()

    def test_insights_budget_query_is_scoped_by_owner_and_month(self):
        self.query_result.mappings.return_value = [ROW]
        self.assertEqual(self.service.get_budgets_for_month(2026, 12)[0].id, BUDGET_ID)
        self.db.execute.assert_called_once()
        sql, params = _compile(self.db.execute.call_args.args[0])
        self.assertIn("WHERE budgets.user_id =", sql)
        self.assertIn("AND budgets.year =", sql)
        self.assertIn("AND budgets.month =", sql)
        self.assertEqual(params["user_id_1"], USER_ID)
        self.assertEqual((params["year_1"], params["month_1"]), (2026, 12))
        self.db.commit.assert_not_called()

    def test_duplicate_create_never_inserts(self):
        self.db.scalar.return_value = True
        with self.assertRaises(DuplicateBudgetError):
            self.service.create_budget(BudgetCreate.model_validate(BUDGET_BODY))
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()

    def test_list_aggregates_live_pkr_expenses_in_one_scoped_paginated_query(self):
        self.query_result.mappings.return_value = [ROW, {**ROW, "id": uuid4()}]
        self.assertEqual(len(self.service.get_budgets(skip=4, limit=2)), 2)
        self.db.execute.assert_called_once()
        sql, params = _compile(self.db.execute.call_args.args[0])
        for fragment in (
            "JOIN LATERAL",
            "coalesce(sum(expenses.amount)",
            "expenses.user_id = budgets.user_id",
            "expenses.category = budgets.category",
            "expenses.currency =",
            "expenses.transaction_date >= make_date(budgets.year, budgets.month,",
            "expenses.transaction_date < CAST(make_date(budgets.year, budgets.month,",
            "+ INTERVAL '1 month' AS DATE)",
            "budgets.budget_limit - spending.total_spent AS remaining_budget",
            "WHERE budgets.user_id =",
            "ORDER BY budgets.year DESC, budgets.month DESC, budgets.id DESC",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, sql)
        self.assertEqual(params["currency_1"], "PKR")
        self.assertEqual(params["coalesce_1"], Decimal("0"))
        self.assertEqual(params["make_date_1"], 1)
        self.assertEqual(params["user_id_1"], USER_ID)
        self.assertEqual((params["param_1"], params["param_2"]), (2, 4))

    def test_detail_and_summary_validate_exact_decimal_and_overspending(self):
        detail = self.service.get_budget_by_id(BUDGET_ID)
        self.assertEqual(detail.total_spent, Decimal("12000.25"))
        summary = self.service.get_budget_summary(BUDGET_ID).model_dump(mode="json")
        self.assertEqual(summary["budget_id"], str(BUDGET_ID))
        self.assertEqual(summary["total_spent"], "12000.25")
        self.assertEqual(summary["remaining_budget"], "-2000.25")
        self.assertNotIn("user_id", summary)
        self.db.commit.assert_not_called()

    def test_partial_update_checks_effective_period_excluding_current_budget(self):
        self.query_result.one_or_none.return_value = SimpleNamespace(
            category="Groceries", month=1, year=2026
        )
        self.rows.one.return_value = {**ROW, "month": 1}
        result = self.service.update_budget(BUDGET_ID, BudgetUpdate(month=1))
        sql, params = _compile(self.db.execute.call_args_list[0].args[0])
        self.assertIn("SET month=", sql)
        self.assertNotIn("SET category=", sql)
        self.assertEqual(params["month"], 1)
        self.assertEqual(result.month, 1)
        sql, params = _compile(self.db.scalar.call_args.args[0])
        self.assertIn("budgets.id !=", sql)
        self.assertEqual(set(params.values()), {USER_ID, "Groceries", 1, 2026, BUDGET_ID})
        self.db.commit.assert_called_once_with()

    def test_limit_only_updates_keep_calendar_period_and_read_live_spending(self):
        period = {**ROW, "month": 11, "year": 2026}
        self.query_result.one_or_none.return_value = SimpleNamespace(
            category=period["category"], month=period["month"], year=period["year"],
        )
        for limit, remaining in (
            ("15000.00", "9000.00"), ("8000.00", "2000.00"),
            ("4000.00", "-2000.00"), ("0", "-6000.00"),
            ("6000.0000000000000000000001", "0.0000000000000000000001"),
        ):
            with self.subTest(limit=limit):
                self.db.reset_mock()
                self.rows.one.return_value = {
                    **period, "budget_limit": Decimal(limit), "total_spent": Decimal("6000.00"),
                    "remaining_budget": Decimal(remaining),
                }
                result = self.service.update_budget(BUDGET_ID, BudgetUpdate(budget_limit=limit))
                self.assertEqual((result.id, result.month, result.year), (BUDGET_ID, 11, 2026))
                self.assertEqual((result.total_spent, result.remaining_budget), (
                    Decimal("6000.00"), Decimal(remaining),
                ))
                write, params = _compile(self.db.execute.call_args_list[0].args[0])
                self.assertEqual(write.split(" SET ")[1].split(" WHERE ")[0].split("=")[0], "budget_limit")
                self.assertEqual(params["budget_limit"], Decimal(limit))
                self.assertEqual((params["user_id_1"], params["id_1"]), (USER_ID, BUDGET_ID))
                read, _ = _compile(self.db.execute.call_args_list[1].args[0])
                self.assertIn("expenses.transaction_date >= make_date(budgets.year, budgets.month,", read)
                self.assertIn("INTERVAL '1 month' AS DATE)", read)
                self.db.add.assert_not_called()
                self.db.scalar.assert_not_called()
                self.db.commit.assert_called_once_with()

    def test_later_summaries_requery_expenses_after_edit_and_delete(self):
        self.query_result.one_or_none.return_value = SimpleNamespace(
            category=ROW["category"], month=12, year=2026,
        )
        self.rows.one.return_value = {**ROW, "budget_limit": Decimal("15000")}
        self.service.update_budget(BUDGET_ID, BudgetUpdate(budget_limit="15000"))
        self.rows.one_or_none.side_effect = [
            {**ROW, "budget_limit": Decimal("15000"), "total_spent": Decimal("6001.01"),
             "remaining_budget": Decimal("8998.99")},
            {**ROW, "budget_limit": Decimal("15000"), "total_spent": Decimal("0"),
             "remaining_budget": Decimal("15000")},
        ]
        self.assertEqual(self.service.get_budget_summary(BUDGET_ID).total_spent, Decimal("6001.01"))
        self.assertEqual(self.service.get_budget_summary(BUDGET_ID).total_spent, Decimal("0"))
        for call in self.db.execute.call_args_list[-2:]:
            sql, params = _compile(call.args[0])
            self.assertIn("JOIN LATERAL", sql)
            self.assertEqual(params["id_1"], BUDGET_ID)

    def test_period_edits_can_be_disabled_without_disabling_limit_edits(self):
        service = BudgetService(self.db, USER_ID, _BUDGET, _EXPENSE, allow_period_changes=False)
        for patch in (BudgetUpdate(month=1), BudgetUpdate(year=2027)):
            with self.assertRaises(BudgetPeriodChangeError):
                service.update_budget(BUDGET_ID, patch)
        self.db.execute.assert_not_called()
        self.query_result.one_or_none.return_value = SimpleNamespace(
            category=ROW["category"], month=12, year=2026,
        )
        self.rows.one.return_value = {**ROW, "budget_limit": Decimal("0")}
        self.assertEqual(service.update_budget(BUDGET_ID, BudgetUpdate(budget_limit=0)).budget_limit, 0)

    def test_duplicate_period_patch_rolls_back(self):
        self.query_result.one_or_none.return_value = SimpleNamespace(
            category="Groceries", month=1, year=2026
        )
        self.db.scalar.return_value = True
        with self.assertRaises(DuplicateBudgetError):
            self.service.update_budget(BUDGET_ID, BudgetUpdate(month=1))
        self.db.rollback.assert_called_once_with()
        self.db.commit.assert_not_called()

    def test_delete_and_missing_or_non_owned_operations_are_scoped(self):
        other_user = uuid4()
        self.rows.one_or_none.return_value = None
        self.query_result.one_or_none.return_value = None
        self.db.scalar.return_value = None
        service = BudgetService(self.db, other_user, _BUDGET, _EXPENSE)
        self.assertIsNone(service.get_budget_by_id(BUDGET_ID))
        self.assertIsNone(service.get_budget_summary(BUDGET_ID))
        self.assertIsNone(service.update_budget(BUDGET_ID, BudgetUpdate(budget_limit=0)))
        self.assertFalse(service.delete_budget(BUDGET_ID))
        for call in [*self.db.execute.call_args_list, self.db.scalar.call_args]:
            sql, params = _compile(call.args[0])
            self.assertIn("WHERE budgets.user_id =", sql)
            self.assertIn("AND budgets.id =", sql)
            self.assertEqual(params["user_id_1"], other_user)
            self.assertEqual(params["id_1"], BUDGET_ID)

        self.db.scalar.return_value = BUDGET_ID
        self.assertTrue(self.service.delete_budget(BUDGET_ID))

    def test_only_the_named_postgres_unique_violation_is_a_conflict(self):
        for constraint, expected in (
            ("uq_budgets_user_category_month_year", DuplicateBudgetError),
            ("unrelated_unique", IntegrityError),
        ):
            with self.subTest(constraint=constraint):
                self.db.reset_mock()
                original = Exception("internal database detail")
                original.sqlstate = "23505"
                original.diag = SimpleNamespace(constraint_name=constraint)
                self.db.commit.side_effect = IntegrityError("INSERT", {}, original)
                with self.assertRaises(expected):
                    self.service.create_budget(BudgetCreate.model_validate(BUDGET_BODY))
                self.db.rollback.assert_called_once_with()

    def test_write_failure_rolls_back_and_preserves_error(self):
        self.db.execute.side_effect = SQLAlchemyError("write failed")
        with self.assertRaises(SQLAlchemyError):
            self.service.update_budget(BUDGET_ID, BudgetUpdate(budget_limit=0))
        self.db.rollback.assert_called_once_with()
        self.db.commit.assert_not_called()


class BudgetAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = Mock(spec=BudgetService)
        app = FastAPI()
        app.include_router(router)

        def provider(authorization: Annotated[str | None, Header()] = None):
            if authorization != AUTH["Authorization"]:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return self.service

        app.dependency_overrides[get_budget_service] = provider
        self.client = await self.enterAsyncContext(
            AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        )

    async def test_successful_crud_and_summary(self):
        budget = BudgetResponse.model_validate(ROW)
        self.service.create_budget.return_value = budget
        self.service.get_budgets.return_value = [budget]
        self.service.get_budget_by_id.return_value = budget
        self.service.update_budget.return_value = budget
        self.service.delete_budget.return_value = True
        self.service.get_budget_summary.return_value = BudgetSummary.model_validate(
            {**ROW, "budget_id": BUDGET_ID}
        )
        response = await self.client.post("/budgets", headers=AUTH, json=BUDGET_BODY)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["budget_limit"], "10000.00")
        response = await self.client.get("/budgets?skip=4&limit=2", headers=AUTH)
        self.assertEqual(response.status_code, 200)
        self.service.get_budgets.assert_called_once_with(skip=4, limit=2)
        self.assertEqual((await self.client.get(BUDGET_PATH, headers=AUTH)).status_code, 200)
        response = await self.client.patch(BUDGET_PATH, headers=AUTH, json={"month": 1})
        self.assertEqual(response.status_code, 200)
        budget_id, changes = self.service.update_budget.call_args.args
        self.assertEqual(budget_id, BUDGET_ID)
        self.assertEqual(changes.model_dump(exclude_unset=True), {"month": 1})
        response = await self.client.get(f"{BUDGET_PATH}/summary", headers=AUTH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["remaining_budget"], "-2000.25")
        response = await self.client.delete(BUDGET_PATH, headers=AUTH)
        self.assertEqual((response.status_code, response.content), (204, b""))

    async def test_all_routes_require_authentication(self):
        for method, path, body in (
            ("POST", "/budgets", BUDGET_BODY),
            ("GET", "/budgets", None),
            ("GET", BUDGET_PATH, None),
            ("PATCH", BUDGET_PATH, {"month": 1}),
            ("DELETE", BUDGET_PATH, None),
            ("GET", f"{BUDGET_PATH}/summary", None),
        ):
            with self.subTest(method=method, path=path):
                self.assertEqual((await self.client.request(method, path, json=body)).status_code, 401)
        self.assertEqual(self.service.method_calls, [])

    async def test_invalid_inputs_are_rejected_before_service_calls(self):
        for method, path, body in (
            ("POST", "/budgets", {**BUDGET_BODY, "budget_limit": "-0.01"}),
            ("POST", "/budgets", {**BUDGET_BODY, "user_id": str(USER_ID)}),
            ("PATCH", BUDGET_PATH, {"user_id": str(USER_ID)}),
            ("PATCH", BUDGET_PATH, {"month": None}),
            ("GET", "/budgets/invalid/summary", None),
            ("GET", "/budgets?limit=101", None),
        ):
            with self.subTest(method=method, path=path, body=body):
                response = await self.client.request(method, path, headers=AUTH, json=body)
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.method_calls, [])

    async def test_missing_or_non_owned_budget_responses_are_uniform(self):
        self.service.get_budget_by_id.return_value = None
        self.service.get_budget_summary.return_value = None
        self.service.update_budget.return_value = None
        self.service.delete_budget.return_value = False
        for method, path, body in (
            ("GET", BUDGET_PATH, None),
            ("GET", f"{BUDGET_PATH}/summary", None),
            ("PATCH", BUDGET_PATH, {"month": 1}),
            ("DELETE", BUDGET_PATH, None),
        ):
            with self.subTest(method=method, path=path):
                response = await self.client.request(method, path, headers=AUTH, json=body)
                self.assertEqual((response.status_code, response.json()), (404, {"detail": "Budget not found"}))

    async def test_duplicate_create_and_patch_return_conflict(self):
        self.service.create_budget.side_effect = DuplicateBudgetError
        self.service.update_budget.side_effect = DuplicateBudgetError
        created = await self.client.post("/budgets", headers=AUTH, json=BUDGET_BODY)
        updated = await self.client.patch(BUDGET_PATH, headers=AUTH, json={"month": 1})
        self.assertEqual((created.status_code, updated.status_code), (409, 409))
        self.assertEqual(created.json(), updated.json())

    async def test_disabled_period_update_returns_422(self):
        self.service.update_budget.side_effect = BudgetPeriodChangeError("Budget period is locked")
        response = await self.client.patch(BUDGET_PATH, headers=AUTH, json={"month": 1})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"detail": "Budget period is locked"})
