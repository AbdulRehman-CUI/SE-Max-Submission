import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session


class MergedAppTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        backend = str(Path(__file__).resolve().parents[1])
        with patch.object(sys, "path", [backend, *sys.path]), patch.dict(os.environ, {
            "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:1/spendsense_test",
            "SECRET_KEY": "synthetic-integration-test-secret-not-for-deployment",
            "DEBUG": "false",
            "GEMINI_API_KEY": "",
        }):
            cls.main = import_module("app.main")
            cls.security = import_module("app.utils.security")

    async def asyncSetUp(self):
        self.owner = uuid4()
        self.other = uuid4()
        self.session = Mock(spec=Session)
        now = datetime.now(timezone.utc)
        users = {
            self.owner: self.main.User(id=self.owner, is_active=True, username="owner", email="owner@example.com", created_at=now),
            self.other: self.main.User(id=self.other, is_active=True, username="other", email="other@example.com", created_at=now),
        }

        def user_filter(condition):
            return SimpleNamespace(first=lambda: users.get(condition.right.value))

        self.session.query.return_value.filter.side_effect = user_filter
        self.session.execute.return_value.mappings.return_value = []
        self.session.scalar.return_value = None
        self.session.scalars.return_value.one_or_none.return_value = None
        app = self.main.app
        self.enterContext(patch.dict(app.dependency_overrides, {self.main.get_db: lambda: self.session}))
        self.enterContext(patch.object(app, "state", type(app.state)()))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver",
        ))

    def bearer(self, user_id, expires_delta=None):
        token = self.security.create_access_token(str(user_id), expires_delta)
        return {"Authorization": f"Bearer {token}"}

    async def test_real_jwt_dependency_accepts_signed_tokens_and_rejects_missing_invalid_and_expired(self):
        accepted = await self.client.get("/auth/me", headers=self.bearer(self.owner))
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["id"], str(self.owner))
        for headers in ({}, {"Authorization": "Bearer invalid"}, self.bearer(self.owner, timedelta(minutes=-5))):
            for path in ("/expenses", "/budgets", "/analytics/insights", "/v2/analytics/monthly?year=2025&month=1"):
                with self.subTest(path=path):
                    response = await self.client.get(path, headers=headers)
                    self.assertEqual(response.status_code, 401)
        self.session.execute.assert_not_called()

    async def test_expense_and_budget_use_authenticated_uuid_in_read_and_write_queries(self):
        item_id = uuid4()
        headers = self.bearer(self.other)
        read = await self.client.get(f"/expenses/{item_id}", headers=headers)
        self.assertEqual(read.status_code, 404)
        update = await self.client.put(f"/expenses/{item_id}", headers=headers, json={"amount": "12.30"})
        self.assertEqual(update.status_code, 404)
        for call in self.session.scalars.call_args_list:
            params = call.args[0].compile(dialect=postgresql.dialect()).params
            self.assertEqual((params["user_id_1"], params["id_1"]), (self.other, item_id))
        self.session.execute.return_value.mappings.return_value = Mock()
        self.session.execute.return_value.mappings.return_value.one_or_none.return_value = None
        response = await self.client.get(f"/budgets/{item_id}/summary", headers=headers)
        self.assertEqual(response.status_code, 404)
        params = self.session.execute.call_args.args[0].compile(dialect=postgresql.dialect()).params
        self.assertEqual((params["user_id_1"], params["id_1"]), (self.other, item_id))

    async def test_expense_create_assigns_real_model_owner_and_legacy_alias(self):
        def assign_defaults():
            expense = self.session.add.call_args.args[0]
            expense.id = uuid4()
            expense.created_at = datetime.now(timezone.utc)

        self.session.flush.side_effect = assign_defaults
        response = await self.client.post("/expenses", headers=self.bearer(self.owner), json={
            "amount": "1250.50", "category": "Groceries", "transaction_date": "2026-11-10",
        })
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["expense_id"], result["id"])
        self.assertEqual(result["user_id"], str(self.owner))
        self.assertEqual(result["amount"], "1250.50")
        self.session.commit.assert_called_once_with()

    async def test_storage_precision_rejects_rounding_before_writing(self):
        headers = self.bearer(self.owner)
        expense = await self.client.post("/expenses", headers=headers, json={
            "amount": "12.345", "category": "Food", "transaction_date": "2026-11-10",
        })
        budget = await self.client.put(f"/budgets/{uuid4()}", headers=headers, json={"budget_limit": "12.345"})
        self.assertEqual((expense.status_code, budget.status_code), (422, 422))
        self.session.add.assert_not_called()
        self.session.execute.assert_not_called()
        self.session.commit.assert_not_called()

    async def test_static_parsing_routes_reuse_one_provider_and_do_not_write(self):
        provider = SimpleNamespace(extract=AsyncMock(side_effect=[
            json.dumps({"status": "single", "amount": "500", "currency": "PKR", "currency_evidence": "PKR",
                        "category": "Food", "description": "lunch", "transaction_date": "2026-11-10",
                        "relative_date": None, "payment_method": None}),
            json.dumps({"category": "Food", "category_evidence": "lunch", "description": "lunch",
                        "payment_method": None, "merchant": None}),
        ]))
        self.main.app.state.gemini_provider = provider
        for path, text in (("parse", "Paid PKR 500 for lunch on 2026-11-10"),
                           ("parse-sms", "HBL: PKR 500 paid for lunch on 10-Nov-2026.")):
            response = await self.client.post(f"/expenses/{path}", headers=self.bearer(self.owner), json={"text": text})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["confirmation_required"])
        self.assertEqual(provider.extract.await_count, 2)
        self.session.add.assert_not_called()
        self.session.commit.assert_not_called()

    async def test_openapi_and_legacy_and_versioned_insight_contracts(self):
        spec = await self.client.get("/openapi.json")
        self.assertEqual(spec.status_code, 200)
        paths = spec.json()["paths"]
        self.assertEqual(set(paths["/expenses/{expense_id}"]), {"get", "put", "patch", "delete"})
        self.assertEqual(set(paths["/budgets/{budget_id}"]), {"get", "put", "patch", "delete"})
        self.assertEqual(set(paths["/expenses/parse"]), {"post"})
        self.assertIn("security", paths["/expenses/parse"]["post"])
        self.assertIn("/analytics/anomalies", paths)
        self.assertIn("/v2/analytics/anomalies/check", paths)
        headers = self.bearer(self.owner)
        legacy = await self.client.get("/analytics/insights", headers=headers)
        self.assertEqual(legacy.status_code, 200, legacy.text)
        self.assertEqual(set(legacy.json()), {"user_id", "insights", "generated_at", "status"})
        self.assertEqual(legacy.json()["status"], "fallback")
        newer = await self.client.get("/v2/analytics/insights?year=2025&month=1", headers=headers)
        self.assertEqual(newer.status_code, 200, newer.text)
        self.assertTrue(newer.json()["is_fallback"])
