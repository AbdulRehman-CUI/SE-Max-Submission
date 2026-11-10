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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.routes.expenses import get_expense_service, router
from backend.app.schemas import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from backend.app.services.expense_service import MAX_SKIP, ExpenseService

USER_ID = uuid4()
EXPENSE_ID = uuid4()
EXPENSE_PATH = f"/expenses/{EXPENSE_ID}"
EXPENSE_BODY = {"amount": "1250.50", "category": "Groceries", "transaction_date": "2026-11-10"}
AUTH = {"Authorization": "Bearer test-user"}
_EXPENSES = table(
    "expenses",
    column("id"),
    column("user_id"),
    column("created_at"),
    *(column(name) for name in ExpenseCreate.model_fields),
)


class _ExpenseStub(SimpleNamespace):
    """Plain record with SQL expression columns for statement compilation."""

    id = _EXPENSES.c.id
    user_id = _EXPENSES.c.user_id
    transaction_date = _EXPENSES.c.transaction_date

    @classmethod
    def __clause_element__(cls):
        return _EXPENSES


def _expense_row(**changes):
    fields = ExpenseCreate.model_validate(EXPENSE_BODY).model_dump()
    fields.update(id=EXPENSE_ID, user_id=USER_ID, created_at=datetime.now(timezone.utc))
    fields.update(changes)
    return SimpleNamespace(**fields)


def _sql(statement):
    compiled = statement.compile(dialect=postgresql.dialect())
    return str(compiled), compiled.params


class ExpenseServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock(spec=Session)
        self.service = ExpenseService(self.db, USER_ID, _ExpenseStub)

    def assert_owned_statement(self, statement, expense_id=EXPENSE_ID, user_id=USER_ID):
        sql, params = _sql(statement)
        self.assertRegex(
            sql,
            r"WHERE expenses\.user_id = %\(user_id_1\)s(?:::UUID)? "
            r"AND expenses\.id = %\(id_1\)s(?:::UUID)?",
        )
        self.assertEqual(params["user_id_1"], user_id)
        self.assertEqual(params["id_1"], expense_id)
        return sql, params

    def test_create_sets_owner_and_preserves_decimal_and_default_currency(self):
        def assign_server_fields():
            row = self.db.add.call_args.args[0]
            row.id = EXPENSE_ID
            row.created_at = datetime.now(timezone.utc)

        self.db.flush.side_effect = assign_server_fields
        response = self.service.create_expense(ExpenseCreate.model_validate(EXPENSE_BODY))

        row = self.db.add.call_args.args[0]
        self.assertEqual(row.user_id, USER_ID)
        self.assertIsInstance(row.amount, Decimal)
        self.assertEqual(row.amount, Decimal("1250.50"))
        self.assertEqual(response.currency, "PKR")
        self.assertEqual(response.id, EXPENSE_ID)
        self.assertEqual([call[0] for call in self.db.method_calls], ["add", "flush", "commit"])

    def test_list_uses_one_scoped_query_with_stable_order_and_pagination(self):
        self.db.scalars.return_value = [_expense_row()]
        results = self.service.get_expenses(skip=5, limit=3)
        self.assertEqual([expense.id for expense in results], [EXPENSE_ID])
        self.db.scalars.assert_called_once()
        sql, params = _sql(self.db.scalars.call_args.args[0])
        self.assertIn("WHERE expenses.user_id = %(user_id_1)s", sql)
        self.assertIn("ORDER BY expenses.transaction_date DESC, expenses.id DESC", sql)
        self.assertRegex(
            sql, r"LIMIT %\(param_1\)s(?:::INTEGER)? OFFSET %\(param_2\)s(?:::INTEGER)?"
        )
        self.assertEqual(params, {"user_id_1": USER_ID, "param_1": 3, "param_2": 5})
        self.db.commit.assert_not_called()

    def test_list_rejects_invalid_pagination_before_querying(self):
        for skip, limit in ((-1, 20), (MAX_SKIP + 1, 20), (0, 0), (0, 101), (True, 20)):
            with self.subTest(skip=skip, limit=limit), self.assertRaises(ValueError):
                self.service.get_expenses(skip=skip, limit=limit)
        self.db.scalars.assert_not_called()

    def test_get_queries_by_owner_and_uuid(self):
        self.db.scalars.return_value.one_or_none.return_value = _expense_row()
        self.assertEqual(self.service.get_expense_by_id(EXPENSE_ID).id, EXPENSE_ID)
        self.assert_owned_statement(self.db.scalars.call_args.args[0])

    def test_patch_writes_only_supplied_fields_including_explicit_null(self):
        self.db.scalars.return_value.one_or_none.return_value = _expense_row(amount=Decimal("4.10"))
        patch = ExpenseUpdate(amount="4.10", description=None)
        self.assertEqual(self.service.update_expense(EXPENSE_ID, patch).amount, Decimal("4.10"))
        sql, params = self.assert_owned_statement(self.db.scalars.call_args.args[0])
        self.assertIn("SET amount=%(amount)s, description=%(description)s WHERE", sql)
        self.assertIsInstance(params["amount"], Decimal)
        self.assertIsNone(params["description"])
        self.db.commit.assert_called_once_with()

    def test_empty_patch_only_reads_the_owned_expense(self):
        self.db.scalars.return_value.one_or_none.return_value = _expense_row()
        self.assertEqual(self.service.update_expense(EXPENSE_ID, ExpenseUpdate()).id, EXPENSE_ID)
        sql, _ = self.assert_owned_statement(self.db.scalars.call_args.args[0])
        self.assertTrue(sql.startswith("SELECT "))
        self.db.commit.assert_not_called()

    def test_delete_targets_only_the_owned_expense(self):
        self.db.scalar.return_value = EXPENSE_ID
        self.assertTrue(self.service.delete_expense(EXPENSE_ID))
        sql, _ = self.assert_owned_statement(self.db.scalar.call_args.args[0])
        self.assertTrue(sql.startswith("DELETE FROM expenses WHERE"))
        self.assertIn("RETURNING expenses.id", sql)
        self.db.commit.assert_called_once_with()

    def test_unknown_and_other_users_ids_have_the_same_result(self):
        self.db.scalars.return_value.one_or_none.return_value = None
        self.db.scalar.return_value = None
        other_user = uuid4()
        for user_id, expense_id in ((USER_ID, uuid4()), (other_user, EXPENSE_ID)):
            with self.subTest(user_id=user_id, expense_id=expense_id):
                service = ExpenseService(self.db, user_id, _ExpenseStub)
                self.assertIsNone(service.get_expense_by_id(expense_id))
                self.assert_owned_statement(self.db.scalars.call_args.args[0], expense_id, user_id)
                self.assertIsNone(service.update_expense(expense_id, ExpenseUpdate(amount=1)))
                self.assert_owned_statement(self.db.scalars.call_args.args[0], expense_id, user_id)
                self.assertFalse(service.delete_expense(expense_id))
                self.assert_owned_statement(self.db.scalar.call_args.args[0], expense_id, user_id)

    def test_failed_write_rolls_back_and_propagates_the_error(self):
        operations = (
            ("flush", self.service.create_expense, (ExpenseCreate.model_validate(EXPENSE_BODY),)),
            ("scalars", self.service.update_expense, (EXPENSE_ID, ExpenseUpdate(amount=1))),
            ("scalar", self.service.delete_expense, (EXPENSE_ID,)),
            ("commit", self.service.delete_expense, (EXPENSE_ID,)),
        )
        for stage, operation, args in operations:
            with self.subTest(stage=stage):
                self.db.reset_mock(side_effect=True)
                getattr(self.db, stage).side_effect = SQLAlchemyError("test write failure")
                with self.assertRaises(SQLAlchemyError):
                    operation(*args)
                self.db.rollback.assert_called_once_with()
                if stage != "commit":
                    self.db.commit.assert_not_called()


class ExpenseAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = Mock(spec=ExpenseService)
        self.expense = ExpenseResponse.model_validate(_expense_row())
        self.app = FastAPI()
        self.app.include_router(router)

        def test_provider(authorization: Annotated[str | None, Header()] = None):
            if authorization != AUTH["Authorization"]:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return self.service

        self.app.dependency_overrides[get_expense_service] = test_provider
        transport = ASGITransport(app=self.app, raise_app_exceptions=False)
        self.client = await self.enterAsyncContext(
            AsyncClient(transport=transport, base_url="http://testserver")
        )

    async def test_create_returns_201_with_decimal_string_and_pkr(self):
        self.service.create_expense.return_value = self.expense
        response = await self.client.post("/expenses", json=EXPENSE_BODY, headers=AUTH)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["amount"], "1250.50")
        self.assertEqual(response.json()["currency"], "PKR")
        self.service.create_expense.assert_called_once_with(ExpenseCreate.model_validate(EXPENSE_BODY))

    async def test_list_returns_200_and_forwards_pagination(self):
        self.service.get_expenses.return_value = [self.expense]
        for query, skip, limit in (("", 0, 20), ("?skip=5&limit=3", 5, 3)):
            with self.subTest(query=query):
                response = await self.client.get(f"/expenses{query}", headers=AUTH)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()[0]["id"], str(EXPENSE_ID))
                self.service.get_expenses.assert_called_with(skip=skip, limit=limit)

    async def test_get_patch_and_delete_success_statuses(self):
        self.service.get_expense_by_id.return_value = self.expense
        self.service.update_expense.return_value = self.expense
        self.service.delete_expense.return_value = True
        response = await self.client.get(EXPENSE_PATH, headers=AUTH)
        self.assertEqual(response.status_code, 200)
        self.service.get_expense_by_id.assert_called_once_with(EXPENSE_ID)

        response = await self.client.patch(
            EXPENSE_PATH, json={"description": None}, headers=AUTH
        )
        self.assertEqual(response.status_code, 200)
        expense_id, patch = self.service.update_expense.call_args.args
        self.assertEqual(expense_id, EXPENSE_ID)
        self.assertEqual(patch.model_dump(exclude_unset=True), {"description": None})

        response = await self.client.delete(EXPENSE_PATH, headers=AUTH)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.service.delete_expense.assert_called_once_with(EXPENSE_ID)

    async def test_every_endpoint_requires_authentication(self):
        requests = (
            ("POST", "/expenses", EXPENSE_BODY),
            ("GET", "/expenses", None),
            ("GET", EXPENSE_PATH, None),
            ("PATCH", EXPENSE_PATH, {"description": None}),
            ("DELETE", EXPENSE_PATH, None),
        )
        for method, path, body in requests:
            with self.subTest(method=method, path=path):
                response = await self.client.request(method, path, json=body)
                self.assertEqual(response.status_code, 401)
        response = await self.client.get(
            "/expenses", headers={"Authorization": "Bearer invalid"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.method_calls, [])

    async def test_missing_or_non_owned_expenses_return_identical_404_responses(self):
        self.service.get_expense_by_id.return_value = None
        self.service.update_expense.return_value = None
        self.service.delete_expense.return_value = False
        for method in ("GET", "PATCH", "DELETE"):
            for path in (EXPENSE_PATH, f"/expenses/{uuid4()}"):
                with self.subTest(method=method, path=path):
                    body = {"amount": 2} if method == "PATCH" else None
                    response = await self.client.request(
                        method, path, json=body, headers=AUTH
                    )
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.json(), {"detail": "Expense not found"})

    async def test_invalid_inputs_never_reach_the_service(self):
        requests = [
            ("POST", "/expenses", {**EXPENSE_BODY, "amount": amount})
            for amount in (0, "-0.01", 0.1)
        ]
        requests.extend([
            ("POST", "/expenses", {**EXPENSE_BODY, "user_id": str(uuid4())}),
            ("PATCH", EXPENSE_PATH, {"user_id": str(uuid4())}),
            ("PATCH", EXPENSE_PATH, {"id": str(uuid4())}),
            ("PATCH", EXPENSE_PATH, {"amount": None}),
            ("PATCH", "/expenses/invalid-id", {"amount": 1}),
            ("GET", "/expenses/invalid-id", None),
            ("DELETE", "/expenses/invalid-id", None),
            ("GET", "/expenses?skip=-1", None),
            ("GET", "/expenses?limit=101", None),
        ])
        for method, path, body in requests:
            with self.subTest(method=method, path=path, body=body):
                response = await self.client.request(method, path, json=body, headers=AUTH)
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.method_calls, [])

    async def test_unexpected_error_returns_500_without_database_details(self):
        self.service.create_expense.side_effect = SQLAlchemyError("private SQL details")
        response = await self.client.post("/expenses", json=EXPENSE_BODY, headers=AUTH)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private SQL details", response.text)

    async def test_router_fails_closed_when_integration_is_missing(self):
        self.app.dependency_overrides.clear()
        response = await self.client.get("/expenses", headers=AUTH)
        self.assertEqual(response.status_code, 503)
