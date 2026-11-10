import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from pydantic import ValidationError

from backend.app.schemas import (
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
    ExpenseCreate,
    ExpenseParseRequest,
    ExpenseParseResponse,
    ExpenseResponse,
    ExpenseUpdate,
    SMSParseRequest,
    SMSParseResponse,
)


class SchemaTests(unittest.TestCase):
    expense = {
        "amount": "1234567890.12345678901234567890",
        "category": "  Groceries  ",
        "transaction_date": "2026-11-10",
    }
    budget = {"category": "Groceries", "budget_limit": "5000.00", "month": 11, "year": 2026}

    def test_expense_create_preserves_decimal_precision_and_defaults_to_pkr(self):
        expense = ExpenseCreate.model_validate(self.expense)
        self.assertEqual(expense.amount, Decimal(self.expense["amount"]))
        self.assertEqual(expense.model_dump(mode="json")["amount"], self.expense["amount"])
        self.assertEqual(expense.category, "Groceries")
        self.assertEqual(expense.transaction_date, date(2026, 11, 10))
        self.assertEqual(expense.currency, "PKR")
        self.assertEqual(ExpenseCreate(**self.expense, currency=" usd ").currency, "USD")

    def test_expense_rejects_invalid_amounts(self):
        for value in ("-1.00", 0, "NaN", "Infinity", 0.1, True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ExpenseCreate.model_validate({**self.expense, "amount": value})

    def test_expense_rejects_invalid_strings_and_dates(self):
        invalid = {
            "category": "   ",
            "currency": "PKR1",
            "payment_method": "   ",
            "transaction_date": "2026-11-10T00:00:00Z",
        }
        for field, value in invalid.items():
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ExpenseCreate.model_validate({**self.expense, field: value})

    def test_partial_expense_update_distinguishes_omission_from_null(self):
        self.assertEqual(ExpenseUpdate().model_dump(exclude_unset=True), {})
        update = ExpenseUpdate(amount="12.34", description=None)
        self.assertEqual(
            update.model_dump(exclude_unset=True),
            {"amount": Decimal("12.34"), "description": None},
        )
        for field in ("amount", "category", "currency", "transaction_date"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ExpenseUpdate.model_validate({field: None})

    def test_valid_budget_creation_including_zero_limit(self):
        budget = BudgetCreate.model_validate(self.budget)
        self.assertEqual(budget.budget_limit, Decimal("5000.00"))
        self.assertEqual((budget.month, budget.year), (11, 2026))
        self.assertEqual(BudgetCreate(**{**self.budget, "budget_limit": 0}).budget_limit, 0)

    def test_budget_rejects_invalid_periods_and_limits(self):
        invalid_values = {
            "month": (0, 13, "11", True),
            "year": (0, 10000, 2026.0, "2026"),
            "budget_limit": ("-0.01", "Infinity", 0.01),
        }
        for field, values in invalid_values.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    BudgetCreate.model_validate({**self.budget, field: value})

    def test_partial_budget_update(self):
        self.assertEqual(BudgetUpdate().model_dump(exclude_unset=True), {})
        self.assertEqual(BudgetUpdate(month=12).model_dump(exclude_unset=True), {"month": 12})
        for field, value in (("budget_limit", None), ("month", 13)):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                BudgetUpdate.model_validate({field: value})

    def test_create_models_require_business_fields_and_reject_client_ownership(self):
        for model, data in ((ExpenseCreate, self.expense), (BudgetCreate, self.budget)):
            with self.subTest(model=model.__name__):
                with self.assertRaises(ValidationError) as error:
                    model.model_validate({})
                self.assertEqual({item["loc"][0] for item in error.exception.errors()}, set(data))
                with self.assertRaises(ValidationError):
                    model.model_validate({**data, "user_id": str(uuid4())})

    def test_expense_response_validates_orm_attributes_and_serializes_uuids(self):
        expense = SimpleNamespace(
            **ExpenseCreate.model_validate(self.expense).model_dump(),
            id=uuid4(),
            user_id=uuid4(),
            created_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
        )
        response = ExpenseResponse.model_validate(expense)
        payload = response.model_dump(mode="json")
        self.assertIsInstance(response.id, UUID)
        self.assertEqual(payload["id"], str(expense.id))
        self.assertEqual(payload["user_id"], str(expense.user_id))
        self.assertEqual(payload["transaction_date"], "2026-11-10")
        self.assertEqual(payload["amount"], self.expense["amount"])
        for field, value in (("id", "invalid"), ("created_at", datetime(2026, 11, 10))):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ExpenseResponse.model_validate({**vars(expense), field: value})
        del expense.currency
        with self.assertRaises(ValidationError):
            ExpenseResponse.model_validate(expense)

    def test_budget_response_accepts_rows_without_calculated_fields(self):
        budget = SimpleNamespace(
            **BudgetCreate.model_validate(self.budget).model_dump(),
            id=uuid4(),
            user_id=uuid4(),
            created_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
        )
        response = BudgetResponse.model_validate(budget)
        self.assertIsNone(response.total_spent)
        self.assertIsNone(response.remaining_budget)
        payload = BudgetResponse.model_validate(
            {**vars(budget), "total_spent": "5000.05", "remaining_budget": "-0.05"}
        ).model_dump(mode="json")
        self.assertEqual(payload["total_spent"], "5000.05")
        self.assertEqual(payload["remaining_budget"], "-0.05")

    def test_parsing_requests_trim_text_and_require_nonblank_strings(self):
        requests = (
            (ExpenseParseRequest, "Spent 450 PKR on lunch"),
            (SMSParseRequest, "Wallet debit: PKR 450.00\nTransaction ID: example"),
        )
        for model, message in requests:
            with self.subTest(model=model.__name__):
                self.assertEqual(model(text=f"  {message}  ").text, message)
                for data in ({}, {"text": " \n"}, {"text": 450}):
                    with self.subTest(data=data), self.assertRaises(ValidationError):
                        model.model_validate(data)

    def test_parsing_responses_report_missing_required_fields_and_require_confirmation(self):
        for model in (ExpenseParseResponse, SMSParseResponse):
            with self.subTest(model=model.__name__):
                draft = model(extracted_fields={"amount": "450.00"}).model_dump(mode="json")
                self.assertEqual(draft["extracted_fields"]["amount"], "450.00")
                self.assertIsNone(draft["extracted_fields"]["currency"])
                self.assertEqual(draft["missing_fields"], ["category", "transaction_date"])
                self.assertIs(draft["confirmation_required"], True)
                complete = model(extracted_fields=self.expense)
                self.assertEqual(complete.missing_fields, [])
                self.assertIs(complete.confirmation_required, True)
                with self.assertRaises(ValidationError):
                    model(extracted_fields={}, confirmation_required=False)


if __name__ == "__main__":
    unittest.main()
