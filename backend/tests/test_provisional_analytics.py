import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import Mock
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app.routes.budgets import get_budget_service, router as budget_router
from backend.app.routes.expenses import router as expense_router
from backend.app.routes.provisional_analytics import get_spending_analytics, router as analytics_router
from backend.app.services.budget_service import BudgetService
from backend.app.services.spending_analytics_service import SpendingAnalyticsService, SpendingRecord

OWNER = uuid4()
OTHER = uuid4()
AUTH = {"Authorization": "Bearer synthetic-owner"}
PERIOD = "year=2025&month=1"
BASE = "/api/analytics"
CANDIDATE = {"amount": "2000", "category": "Food", "transaction_date": "2025-01-15"}


def expense(amount: str, day: date, user_id=OWNER):
    return SpendingRecord(
        uuid4(), user_id, day, datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
        "Food", "PKR", Decimal(amount),
    )


class ProvisionalAnalyticsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repository = Mock()
        self.rows = [expense("100", date(2024, 12, day)) for day in (1, 5, 10, 15, 31)]
        self.rows += [expense("2000.00000000000000000000001", date(2025, 1, 10)),
                      expense("90000", date(2025, 1, 12), OTHER)]
        self.repository.expenses.side_effect = lambda *args, **kwargs: iter(self.rows)
        self.budgets = Mock(spec=BudgetService)
        self.budgets.get_budgets_for_month.return_value = []
        self.app = FastAPI()
        bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

        def current_user(token: Annotated[str, Depends(bearer)]):
            if token == "synthetic-owner":
                return OWNER
            if token == "synthetic-other":
                return OTHER
            raise HTTPException(401, "Unauthorized")

        def provide_analytics(user_id: Annotated[object, Depends(current_user)]):
            return SpendingAnalyticsService(self.repository, user_id)

        def provide_budgets(user_id: Annotated[object, Depends(current_user)]):
            return self.budgets

        for router in (budget_router, expense_router, analytics_router):
            self.app.include_router(router, prefix="/api", dependencies=[Depends(current_user)])
        self.app.dependency_overrides[get_spending_analytics] = provide_analytics
        self.app.dependency_overrides[get_budget_service] = provide_budgets
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(app=self.app, raise_app_exceptions=False),
            base_url="http://testserver",
        ))

    async def test_openapi_schema_and_status_contract_with_all_finance_routers(self):
        paths = self.app.openapi()["paths"]
        self.assertEqual(sum(map(len, paths.values())), 18)
        for route in ("/api/expenses/parse", "/api/expenses/parse-sms"):
            self.assertEqual(set(paths[route]), {"post"})
        expected = {
            "/monthly": ("get", "MonthlySpendingSummary"),
            "/categories": ("get", "CategorySpending"),
            "/trends": ("get", "MonthlySpendingTrend"),
            "/anomalies/check": ("post", "AnomalyResult"),
            "/insights": ("get", "FinancialInsightsResponse"),
        }
        for path, (method, model) in expected.items():
            with self.subTest(path=path):
                operation = paths[BASE + path][method]
                self.assertIn({"OAuth2PasswordBearer": []}, operation["security"])
                schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
                if path in ("/categories", "/trends"):
                    self.assertEqual(schema["type"], "array")
                    schema = schema["items"]
                self.assertEqual(schema["$ref"], f"#/components/schemas/{model}")

    async def test_missing_and_invalid_test_bearer_reject_all_analytics_operations(self):
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            for path in ("monthly", "categories", "trends", "insights", "anomalies/check"):
                with self.subTest(headers=headers, path=path):
                    if path == "anomalies/check":
                        response = await self.client.post(f"{BASE}/{path}", json=CANDIDATE, headers=headers)
                    else:
                        response = await self.client.get(f"{BASE}/{path}?{PERIOD}", headers=headers)
                    self.assertEqual(response.status_code, 401)
        self.repository.expenses.assert_not_called()

    async def test_monthly_categories_and_trends_use_owner_scope_and_exact_month_boundaries(self):
        first = await self.client.get(f"{BASE}/monthly?{PERIOD}&user_id={OTHER}", headers=AUTH)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["total_spent"], "2000.00000000000000000000001")
        self.assertEqual(first.json()["through_date"], "2025-01-31")
        self.assertEqual(self.repository.expenses.call_args.args[0], OWNER)
        second = await self.client.get(f"{BASE}/monthly?{PERIOD}", headers={"Authorization": "Bearer synthetic-other"})
        self.assertEqual(second.json()["total_spent"], "90000")
        categories = await self.client.get(f"{BASE}/categories?{PERIOD}", headers=AUTH)
        self.assertEqual(categories.json(), first.json()["categories"])
        trend = await self.client.get(f"{BASE}/trends?months=2&end_month=2025-01-01", headers=AUTH)
        self.assertEqual([point["month"] for point in trend.json()], [12, 1])
        self.assertEqual(trend.json()[1]["change_percentage"], "300.00")

    async def test_anomaly_is_read_only_and_insights_report_the_scoped_latest_alert(self):
        result = await self.client.post(f"{BASE}/anomalies/check", json=CANDIDATE, headers=AUTH)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "unusual")
        self.assertEqual(result.json()["sample_count"], 6)
        result = await self.client.post(
            f"{BASE}/anomalies/check", json=CANDIDATE, headers={"Authorization": "Bearer synthetic-other"},
        )
        self.assertEqual(result.json()["status"], "insufficient_history")
        response = await self.client.get(f"{BASE}/insights?{PERIOD}", headers=AUTH)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual((data["generated_by"], data["is_fallback"]), ("deterministic", True))
        self.assertEqual(data["warnings"][0]["type"], "anomaly")
        self.assertNotIn("90000", response.text)
        self.budgets.get_budgets_for_month.assert_called_once_with(2025, 1)
        self.assertTrue(all(call[0] == "expenses" for call in self.repository.method_calls))

    async def test_invalid_fields_period_and_unbounded_decimal_are_validation_errors(self):
        for body in ({**CANDIDATE, "user_id": str(OTHER)}, {**CANDIDATE, "amount": "1e100000000"},
                     {**CANDIDATE, "amount": 1.23}, {**CANDIDATE, "currency": "USD"}):
            response = await self.client.post(f"{BASE}/anomalies/check", json=body, headers=AUTH)
            self.assertEqual(response.status_code, 422)
        for query in ("year=9999&month=12", "year=2025&month=0"):
            response = await self.client.get(f"{BASE}/monthly?{query}", headers=AUTH)
            self.assertEqual(response.status_code, 422)
        self.repository.expenses.assert_not_called()

    async def test_database_failures_are_not_presented_as_insights_fallback(self):
        self.repository.expenses.side_effect = SQLAlchemyError("private database detail")
        response = await self.client.get(f"{BASE}/insights?{PERIOD}", headers=AUTH)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private database detail", response.text)

    async def test_mismatched_budget_provider_fails_closed(self):
        self.budgets.get_budgets_for_month.return_value = [SimpleNamespace(user_id=OTHER)]
        response = await self.client.get(f"{BASE}/insights?{PERIOD}", headers=AUTH)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(str(OTHER), response.text)

    async def test_latest_anomaly_excludes_future_insert_and_other_owner(self):
        service = SpendingAnalyticsService(self.repository, OWNER)
        reference = datetime(2025, 1, 15, tzinfo=timezone.utc)
        self.rows.append(replace(expense("100000", date(2025, 1, 13)),
                                 created_at=datetime(2025, 1, 20, tzinfo=timezone.utc)))
        report = service.monthly(2025, 1, reference_datetime=reference)
        anomaly = service.latest_anomaly(report, reference_datetime=reference)
        self.assertEqual(anomaly.amount, Decimal("2000.00000000000000000000001"))
        self.assertEqual(anomaly.sample_count, 5)
