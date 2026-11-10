import json
import os
import unittest
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer
from httpx import ASGITransport, AsyncClient
from sqlalchemy import UniqueConstraint, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.routes.budgets import get_budget_service, router as budget_router
from backend.app.routes.expenses import get_expense_parser, get_expense_service
from backend.app.routes.expenses import router as expense_router
from backend.app.schemas import ExpenseCreate, ExpenseResponse
from backend.app.services.ai_service import ExpenseAIService
from backend.app.services.budget_service import BudgetService
from backend.app.services.expense_service import ExpenseService

_OWNER = uuid4()
_ID = uuid4()
_AUTH = {"Authorization": "Bearer finance-test-user"}
_EXPENSE = {"amount": "500.00", "category": "Food", "transaction_date": "2026-11-10"}
_BUDGET = {"budget_limit": "1500.00", "category": "Food", "month": 11, "year": 2026}
_TEXT = "Paid PKR 500.00 for lunch on 2026-11-10."
_SMS = "HBL: PKR 500.00 paid for lunch on 10-Nov-2026."
_ROUTES = {
    ("/expenses", "post"): (201, "ExpenseCreate", "ExpenseResponse"),
    ("/expenses", "get"): (200, None, "list:ExpenseResponse"),
    ("/expenses/{expense_id}", "get"): (200, None, "ExpenseResponse"),
    ("/expenses/{expense_id}", "patch"): (200, "ExpenseUpdate", "ExpenseResponse"),
    ("/expenses/{expense_id}", "put"): (200, "ExpenseUpdate", "ExpenseResponse"),
    ("/expenses/{expense_id}", "delete"): (204, None, None),
    ("/expenses/parse", "post"): (200, "ExpenseParseRequest", "ExpenseParseResponse"),
    ("/expenses/parse-sms", "post"): (200, "SMSParseRequest", "SMSParseResponse"),
    ("/budgets", "post"): (201, "BudgetCreate", "BudgetResponse"),
    ("/budgets", "get"): (200, None, "list:BudgetResponse"),
    ("/budgets/{budget_id}", "get"): (200, None, "BudgetResponse"),
    ("/budgets/{budget_id}", "patch"): (200, "BudgetUpdate", "BudgetResponse"),
    ("/budgets/{budget_id}", "put"): (200, "BudgetUpdate", "BudgetResponse"),
    ("/budgets/{budget_id}", "delete"): (204, None, None),
    ("/budgets/{budget_id}/summary", "get"): (200, None, "BudgetSummary"),
}


class FinanceRouterIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.expenses = Mock(spec=ExpenseService)
        self.budgets = Mock(spec=BudgetService)
        self.gemini = AsyncMock()
        parser = ExpenseAIService(SimpleNamespace(extract=self.gemini))
        bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

        def authenticated_user(token: Annotated[str, Depends(bearer)]) -> UUID:
            if token != "finance-test-user":
                raise HTTPException(401, "Unauthorized")
            return _OWNER

        def provide_expenses(user_id: Annotated[UUID, Depends(authenticated_user)]):
            self.assertEqual(user_id, _OWNER)
            return self.expenses

        def provide_budgets(user_id: Annotated[UUID, Depends(authenticated_user)]):
            self.assertEqual(user_id, _OWNER)
            return self.budgets

        def provide_parser(user_id: Annotated[UUID, Depends(authenticated_user)]):
            self.assertEqual(user_id, _OWNER)
            return parser

        self.app = FastAPI()
        for router in (expense_router, budget_router):
            self.app.include_router(
                router, prefix="/api", dependencies=[Depends(authenticated_user)]
            )
        self.app.dependency_overrides.update({
            get_expense_service: provide_expenses,
            get_budget_service: provide_budgets,
            get_expense_parser: provide_parser,
        })
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(app=self.app), base_url="http://testserver"
        ))

    async def test_combined_router_openapi_contract(self):
        declared = Counter(
            (route.path, method.lower())
            for router in (expense_router, budget_router)
            for route in router.routes
            for method in route.methods
        )
        self.assertEqual(declared, Counter(_ROUTES.keys()))
        spec = self.app.openapi()
        paths = spec["paths"]
        self.assertEqual({(p.removeprefix("/api"), m) for p in paths for m in paths[p]}, set(_ROUTES))
        self.assertIn("OAuth2PasswordBearer", spec["components"]["securitySchemes"])
        for (path, method), (status, request_model, response_model) in _ROUTES.items():
            with self.subTest(path=path, method=method):
                operation = paths[f"/api{path}"][method]
                self.assertIn({"OAuth2PasswordBearer": []}, operation["security"])
                if request_model is not None:
                    schema = operation["requestBody"]["content"]["application/json"]["schema"]
                    self.assertEqual(schema["$ref"], f"#/components/schemas/{request_model}")
                else:
                    self.assertNotIn("requestBody", operation)
                success = operation["responses"][str(status)]
                if response_model is None:
                    self.assertNotIn("content", success)
                    continue
                schema = success["content"]["application/json"]["schema"]
                if response_model.startswith("list:"):
                    self.assertEqual(schema["type"], "array")
                    schema = schema["items"]
                self.assertEqual(schema["$ref"], f"#/components/schemas/{response_model.removeprefix('list:')}")

    async def test_all_operations_require_the_shared_authentication_boundary(self):
        bodies = {
            "ExpenseCreate": _EXPENSE, "BudgetCreate": _BUDGET,
            "ExpenseUpdate": {}, "BudgetUpdate": {},
            "ExpenseParseRequest": {"text": _TEXT}, "SMSParseRequest": {"text": _SMS},
        }
        for (path, method), (_, request_model, _) in _ROUTES.items():
            path = path.replace("{expense_id}", str(_ID)).replace("{budget_id}", str(_ID))
            with self.subTest(path=path, method=method):
                response = await self.client.request(method, f"/api{path}", json=bodies.get(request_model))
                self.assertEqual(response.status_code, 401)
        self.assertEqual(self.expenses.method_calls, [])
        self.assertEqual(self.budgets.method_calls, [])
        self.gemini.assert_not_awaited()

    async def test_both_static_parse_routes_only_write_on_separate_create_request(self):
        self.gemini.side_effect = [
            json.dumps({
                "status": "single", **_EXPENSE, "currency": "PKR", "currency_evidence": "PKR",
                "description": "lunch", "relative_date": None, "payment_method": None,
            }),
            json.dumps({
                "category": "Food", "category_evidence": "lunch", "description": "lunch",
                "payment_method": None, "merchant": None,
            }),
        ]
        self.expenses.create_expense.return_value = ExpenseResponse.model_validate({
            **_EXPENSE, "id": _ID, "user_id": _OWNER, "currency": "PKR",
            "description": "lunch", "payment_method": None,
            "created_at": datetime(2026, 11, 10, tzinfo=timezone.utc),
        })
        for suffix, text in (("parse", _TEXT), ("parse-sms", _SMS)):
            with self.subTest(suffix=suffix):
                response = await self.client.post(
                    f"/api/expenses/{suffix}", json={"text": text}, headers=_AUTH,
                )
                self.assertEqual(response.status_code, 200)
                draft = response.json()
                self.assertTrue(draft["confirmation_required"])
                self.assertEqual(draft["missing_fields"], [])
                self.assertEqual(draft["extracted_fields"]["amount"], "500.00")
                confirmed = ExpenseCreate.model_validate(draft["extracted_fields"])
        self.assertEqual(self.expenses.method_calls, [])
        self.assertEqual(self.budgets.method_calls, [])

        response = await self.client.post(
            "/api/expenses", json=confirmed.model_dump(mode="json"), headers=_AUTH,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user_id"], str(_OWNER))
        self.expenses.create_expense.assert_called_once_with(confirmed)


_MODELS_MODULE = os.getenv("SPENDSENSE_TEST_MODELS_MODULE")


@unittest.skipUnless(
    _MODELS_MODULE,
    "Developer 1 models and isolated test configuration required; set SPENDSENSE_TEST_MODELS_MODULE",
)
class SharedORMCompatibilityTests(unittest.TestCase):
    """Opt-in mapper and SQL checks. No session or database connection is opened."""

    @classmethod
    def setUpClass(cls):
        cls.models = import_module(_MODELS_MODULE)

    def check_columns(self, model, fields):
        mapper = inspect(model)
        columns = {name: mapper.column_attrs[name].columns[0] for name in fields}
        for name, (python_type, nullable) in fields.items():
            with self.subTest(model=model.__name__, field=name):
                self.assertIs(columns[name].type.python_type, python_type)
                self.assertIs(columns[name].nullable, nullable)
        return columns

    def check_identity(self, columns):
        user_id = inspect(self.models.User).column_attrs["id"].columns[0]
        self.assertIs(user_id.type.python_type, UUID)
        self.assertTrue(columns["id"].primary_key)
        self.assertIn(user_id, {key.column for key in columns["user_id"].foreign_keys})
        self.assertTrue(columns["created_at"].type.timezone)

    def test_expense_mapper_matches_finance_contract(self):
        columns = self.check_columns(self.models.Expense, {
            "id": (UUID, False), "user_id": (UUID, False), "amount": (Decimal, False),
            "category": (str, False), "description": (str, True),
            "transaction_date": (date, False), "currency": (str, False),
            "payment_method": (str, True), "created_at": (datetime, False),
        })
        self.check_identity(columns)

    def test_budget_mapper_has_monthly_unique_key(self):
        columns = self.check_columns(self.models.Budget, {
            "id": (UUID, False), "user_id": (UUID, False), "budget_limit": (Decimal, False),
            "category": (str, False), "month": (int, False), "year": (int, False),
            "created_at": (datetime, False),
        })
        self.check_identity(columns)
        table = inspect(self.models.Budget).local_table
        self.assertTrue(any(
            set(item.columns.keys()) == {"user_id", "category", "month", "year"}
            and item.name == "uq_budget_user_category_month_year"
            for item in [
                *(c for c in table.constraints if isinstance(c, UniqueConstraint)),
                *(index for index in table.indexes if index.unique),
            ]
        ), "Mapped monthly unique key and name must match the service's conflict handler")

    def test_budget_sql_compiles_against_both_shared_mappers(self):
        session = Mock(spec=Session)
        session.execute.return_value.mappings.return_value = []
        service = BudgetService(session, _OWNER, self.models.Budget, self.models.Expense)
        service.get_budgets()
        query = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
        self.assertIn("JOIN LATERAL", str(query))
        self.assertIn(_OWNER, query.params.values())
