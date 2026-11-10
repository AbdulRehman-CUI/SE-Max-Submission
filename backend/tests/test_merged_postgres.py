"""Opt-in test of the merged app against an empty, disposable loopback database."""

import os
import sys
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url


@unittest.skipUnless(os.getenv("SPENDSENSE_TEST_POSTGRES_URL"), "Disposable PostgreSQL opt-in required")
class MergedPostgresTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        dsn = os.environ["SPENDSENSE_TEST_POSTGRES_URL"]
        url = make_url(dsn)
        if (url.drivername != "postgresql+psycopg" or url.host not in {"127.0.0.1", "::1"}
                or not (url.database or "").startswith("spendsense_merge_test") or url.query):
            raise RuntimeError("Use a disposable spendsense_merge_test database on loopback")
        backend = str(Path(__file__).resolve().parents[1])
        with patch.object(sys, "path", [backend, *sys.path]), patch.dict(os.environ, {
            "DATABASE_URL": dsn,
            "SECRET_KEY": "synthetic-postgres-integration-secret-only",
            "DEBUG": "false",
            "GEMINI_API_KEY": "",
        }):
            cls.main = import_module("app.main")
            database = import_module("app.database")
        if database.engine.url != url:
            raise RuntimeError("Run the PostgreSQL test module in a fresh process")
        cls.addClassCleanup(database.engine.dispose)
        with database.engine.connect() as connection:
            if connection.scalar(text("SELECT current_database()")) != url.database:
                raise RuntimeError("Unexpected PostgreSQL database")
            if inspect(connection).get_table_names():
                raise RuntimeError("The PostgreSQL test database must be empty")
        database.Base.metadata.create_all(database.engine)

    async def asyncSetUp(self):
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(app=self.main.app), base_url="http://testserver",
        ))

    async def login_new_user(self, username):
        credentials = {"username": username, "password": "synthetic-test-password"}
        response = await self.client.post("/auth/register", json={
            **credentials, "email": f"{username}@example.com",
        })
        self.assertEqual(response.status_code, 201, response.text)
        response = await self.client.post("/auth/login", json=credentials)
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    async def add_expense(self, headers, amount, day, currency="PKR"):
        response = await self.client.post("/expenses", headers=headers, json={
            "amount": amount, "category": "Food", "transaction_date": day, "currency": currency,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    async def test_integrated_finance_and_jwt_on_postgres(self):
        owner = await self.login_new_user("finance_owner")
        other = await self.login_new_user("finance_other")
        expense_id = await self.add_expense(owner, "1250.50", "2025-12-31")
        await self.add_expense(owner, "250.00", "2026-01-01")
        await self.add_expense(owner, "999.00", "2025-12-31", "USD")
        await self.add_expense(other, "8888.00", "2025-12-31")
        self.assertEqual((await self.client.get(f"/expenses/{expense_id}", headers=other)).status_code, 404)

        payload = {"category": "Food", "budget_limit": "0", "month": 12, "year": 2025}
        response = await self.client.post("/budgets", headers=owner, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        budget = response.json()
        self.assertEqual(budget["id"], budget["budget_id"])
        self.assertEqual(budget["remaining_budget"], "-1250.50")
        self.assertEqual((await self.client.post("/budgets", headers=owner, json=payload)).status_code, 409)
        budget_path = f"/budgets/{budget['id']}"
        self.assertEqual((await self.client.get(budget_path, headers=other)).status_code, 404)
        response = await self.client.put(budget_path, headers=owner, json={"budget_limit": "2000.00"})
        self.assertEqual(response.json()["remaining_budget"], "749.50")
        status = await self.client.get("/analytics/budget-status?year=2025&month=12", headers=owner)
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.json()[0]["total_spent"], "1250.50")

        second = await self.client.post("/budgets", headers=owner, json={**payload, "category": "Transport"})
        self.assertEqual(second.status_code, 201, second.text)
        second_path = f"/budgets/{second.json()['id']}"
        conflict = await self.client.patch(second_path, headers=owner, json={"category": "Food"})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual((await self.client.get(second_path, headers=owner)).json()["category"], "Transport")

        response = await self.client.get("/v2/analytics/trends?months=2&end_month=2026-01-01", headers=owner)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([item["total_spent"] for item in response.json()], ["1250.50", "250.00"])
        categories = await self.client.get("/v2/analytics/categories?year=2025&month=12", headers=owner)
        self.assertEqual(categories.json()[0]["total_spent"], "1250.50")
        insights = await self.client.get("/v2/analytics/insights?year=2025&month=12", headers=owner)
        self.assertEqual(insights.status_code, 200, insights.text)
        self.assertTrue(insights.json()["is_fallback"])
        anomaly = await self.client.post("/v2/analytics/anomalies/check", headers=owner, json={
            "amount": "5000", "category": "Food", "transaction_date": "2026-01-01",
        })
        self.assertEqual(anomaly.json()["status"], "insufficient_history")
        self.assertEqual(anomaly.json()["sample_count"], 1)

        response = await self.client.patch(f"/expenses/{expense_id}", headers=owner, json={"amount": "1000.25"})
        self.assertEqual(response.json()["amount"], "1000.25")
        response = await self.client.get(f"{budget_path}/summary", headers=owner)
        self.assertEqual(response.json()["total_spent"], "1000.25")
        self.assertEqual((await self.client.delete(f"/expenses/{expense_id}", headers=owner)).status_code, 204)
        response = await self.client.get(f"{budget_path}/summary", headers=owner)
        self.assertEqual(response.json()["total_spent"], "0")
        self.assertEqual((await self.client.delete(budget_path, headers=owner)).status_code, 204)
