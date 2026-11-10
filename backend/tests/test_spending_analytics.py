import unittest
from dataclasses import asdict, replace
from datetime import date, datetime, time, timezone
from decimal import Decimal, localcontext
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import column, table
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.services.spending_analytics_service import (
    SpendingAnalyticsService,
    SpendingRecord,
    SQLAlchemySpendingRepository,
)
from backend.app.spending_analytics_schemas import AnomalyCandidate, AnomalyPolicy

OWNER = uuid4()
OTHER_USER = uuid4()
TODAY = date(2026, 11, 10)
REFERENCE = datetime(2026, 11, 9, 20, 30, tzinfo=timezone.utc)  # November 10 in Karachi.


def record(amount, day=date(2026, 11, 1), **fields):
    return SpendingRecord(**{
        "id": uuid4(), "user_id": OWNER, "transaction_date": day,
        "created_at": datetime.combine(day, time(), timezone.utc),
        "category": "Food", "currency": "PKR", "amount": Decimal(amount),
        **fields,
    })


class SpendingAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.repo.expenses.return_value = []
        self.service = SpendingAnalyticsService(self.repo, OWNER)

    def test_monthly_totals_counts_and_category_percentages_reconcile(self):
        self.repo.expenses.return_value = [
            record("5000.00"), record("3000.00"), record("3000.00", category="Transport"),
            record("5000.00", category="Shopping"),
        ]
        summary = self.service.monthly(2026, 11, reference_datetime=REFERENCE)
        self.assertEqual((summary.total_spent, summary.transaction_count, summary.average_expense), (
            Decimal("16000.00"), 4, Decimal("4000.00"),
        ))
        self.assertEqual(
            [(line.category, line.total_spent, line.transaction_count, line.percentage_of_total)
             for line in summary.categories],
            [("Food", Decimal("8000.00"), 2, Decimal("50.00")),
             ("Shopping", Decimal("5000.00"), 1, Decimal("31.25")),
             ("Transport", Decimal("3000.00"), 1, Decimal("18.75"))],
        )
        self.assertEqual(sum(line.total_spent for line in summary.categories), summary.total_spent)
        self.assertEqual(sum(line.percentage_of_total for line in summary.categories), 100)

    def test_equal_categories_have_stable_rounding_and_unknown_category_is_visible(self):
        self.repo.expenses.return_value = [
            record("1", category="Transport"), record("1", category=None), record("1"),
        ]
        summary = self.service.monthly(2026, 11, reference_datetime=REFERENCE)
        self.assertEqual([line.category for line in summary.categories], ["Food", "Transport", None])
        self.assertEqual([line.percentage_of_total for line in summary.categories], [
            Decimal("33.34"), Decimal("33.33"), Decimal("33.33"),
        ])

    def test_scope_excludes_other_users_currencies_and_dates_even_if_repository_overreturns(self):
        self.repo.expenses.return_value = [
            record("10", date(2026, 10, 31)), record("25", date(2026, 11, 1)),
            record("75", TODAY), record("200", date(2026, 11, 11)),
            record("300", user_id=OTHER_USER), record("400", currency="USD"),
        ]
        summary = self.service.monthly(2026, 11, reference_datetime=REFERENCE)
        self.assertEqual(summary.total_spent, Decimal("100"))
        self.assertTrue(summary.is_partial)
        self.assertEqual(summary.through_date, TODAY)
        self.repo.expenses.assert_called_once_with(
            OWNER, "PKR", start=date(2026, 11, 1), end=date(2026, 11, 11), category=None,
        )
        dollars = SpendingAnalyticsService(self.repo, OWNER, currency=" usd ")
        self.assertEqual(dollars.monthly(2026, 11, reference_datetime=REFERENCE).total_spent, 400)

    def test_empty_month_and_zero_spend_do_not_divide_by_zero(self):
        summary = self.service.monthly(2026, 10, reference_datetime=REFERENCE)
        self.assertEqual((summary.total_spent, summary.transaction_count, summary.categories), (0, 0, []))
        self.assertIsNone(summary.average_expense)
        self.repo.expenses.return_value = [record("0")]
        summary = self.service.monthly(2026, 11, reference_datetime=REFERENCE)
        self.assertEqual(summary.categories[0].percentage_of_total, Decimal("0.00"))
        self.assertEqual(summary.average_expense, 0)

    def test_trends_fill_gaps_and_annotate_current_month_with_one_range_read(self):
        self.repo.expenses.return_value = [
            record("12000.00", date(2026, 8, 31)), record("15000.00", date(2026, 9, 1)),
            record("18000.00", TODAY), record("9999", date(2026, 11, 11)),
        ]
        points = self.service.trends(4, reference_datetime=REFERENCE)
        self.assertEqual([point.month for point in points], [8, 9, 10, 11])
        self.assertEqual([point.total_spent for point in points], [12000, 15000, 0, 18000])
        self.assertEqual([point.change_amount for point in points], [None, 3000, -15000, 18000])
        self.assertEqual([point.change_percentage for point in points], [None, 25, -100, None])
        self.assertEqual([point.is_partial for point in points], [False, False, False, True])
        self.assertEqual(points[0].through_date, date(2026, 8, 31))
        self.assertEqual(points[-1].categories[0].category, "Food")
        self.repo.expenses.assert_called_once_with(
            OWNER, "PKR", start=date(2026, 8, 1), end=date(2026, 11, 11), category=None,
        )

    def test_december_to_january_rollover_uses_karachi_calendar(self):
        reference = datetime(2026, 12, 31, 20, 0, tzinfo=timezone.utc)
        self.repo.expenses.return_value = [
            record("10", date(2026, 12, 31)), record("11", date(2027, 1, 1)),
            record("99", date(2027, 1, 2)),
        ]
        points = self.service.trends(2, reference_datetime=reference)
        self.assertEqual([(point.year, point.month, point.total_spent) for point in points], [
            (2026, 12, 10), (2027, 1, 11),
        ])
        previous = self.service.trends(1, end_month=date(2026, 12, 15), reference_datetime=reference)[0]
        self.assertFalse(previous.is_partial)
        self.assertEqual(previous.through_date, date(2026, 12, 31))
        self.assertEqual(self.repo.expenses.call_args.kwargs["end"], date(2027, 1, 1))

    def test_exact_decimal_totals_ignore_ambient_precision_and_serialize_as_strings(self):
        self.repo.expenses.return_value = [
            record("100000000000000000000000000000000.00000000000000000001"),
            record("0.00000000000000000001", category="Shopping"),
        ]
        with localcontext() as context:
            context.prec = 6
            summary = self.service.monthly(2026, 11, reference_datetime=REFERENCE)
        data = summary.model_dump(mode="json")
        self.assertEqual(data["total_spent"], "100000000000000000000000000000000.00000000000000000002")
        self.assertEqual(data["average_expense"], "50000000000000000000000000000000.00000000000000000001")
        self.assertEqual([line.percentage_of_total for line in summary.categories], [100, 0])

    def test_future_reporting_periods_and_invalid_windows_fail_without_querying(self):
        for call in (
            lambda: self.service.monthly(2026, 12, reference_datetime=REFERENCE),
            lambda: self.service.trends(0, reference_datetime=REFERENCE),
            lambda: self.service.trends(121, reference_datetime=REFERENCE),
            lambda: self.service.trends(end_month=date(2026, 12, 1), reference_datetime=REFERENCE),
            lambda: self.service.monthly(2026, 11, reference_datetime=datetime(2026, 11, 10)),
        ):
            with self.assertRaises(ValueError):
                call()
        self.repo.expenses.assert_not_called()

    def test_sqlalchemy_adapter_uses_one_owner_currency_category_and_half_open_query(self):
        expense = table("expenses", *(column(field) for field in SpendingRecord.__dataclass_fields__))
        session = Mock(spec=Session)
        fact = record("10")
        session.execute.return_value.mappings.return_value = [asdict(fact)]
        repo = SQLAlchemySpendingRepository(session, expense.c)
        results = list(repo.expenses(
            OWNER, "PKR", start=date(2026, 11, 1), end=date(2026, 12, 1), category="Food",
        ))
        self.assertEqual(results, [fact])
        session.execute.assert_called_once()
        statement = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
        for predicate in (
            "expenses.user_id =", "expenses.currency =", "expenses.category =",
            "expenses.transaction_date >=", "expenses.transaction_date <",
        ):
            self.assertIn(predicate, str(statement))
        self.assertEqual(set(statement.params.values()), {
            OWNER, "PKR", "Food", date(2026, 11, 1), date(2026, 12, 1),
        })


class AnomalyTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.repo.expenses.return_value = [record("200") for _ in range(5)]
        self.service = SpendingAnalyticsService(self.repo, OWNER)

    def check(self, amount, *, day=TODAY, **options):
        candidate = AnomalyCandidate(amount=amount, category="Food", transaction_date=day)
        return self.service.check_anomaly(candidate, reference_datetime=REFERENCE, **options)

    def test_normal_unusual_and_exact_minimum_history_explain_results(self):
        normal = self.check("550")
        unusual = self.check("1200.01")
        self.assertEqual((normal.status, normal.is_unusual), ("normal", False))
        self.assertEqual((unusual.status, unusual.is_unusual, unusual.sample_count), ("unusual", True, 5))
        self.assertTrue(unusual.has_enough_history)
        self.assertEqual((unusual.baseline_amount, unusual.threshold_amount), (200, 600))
        self.assertIn("5 previous Food expenses", unusual.explanation)
        self.assertEqual(unusual.model_dump(mode="json")["amount"], "1200.01")

    def test_history_below_minimum_does_not_imply_normal_spending(self):
        for count in (0, 1, 4):
            with self.subTest(count=count):
                self.repo.expenses.return_value = [record("1") for _ in range(count)]
                result = self.check("99999")
                self.assertEqual((result.status, result.sample_count, result.minimum_history), (
                    "insufficient_history", count, 5,
                ))
                self.assertFalse(result.is_unusual)
                self.assertFalse(result.has_enough_history)
                self.assertIsNone(result.baseline_amount)

    def test_anomaly_history_enforces_category_currency_owner_and_future_cutoffs(self):
        self.repo.expenses.return_value.extend([
            record("999", category="Transport"), record("999", category=None),
            record("999", currency="USD"), record("999", user_id=OTHER_USER),
            record("999", date(2026, 11, 11)),
            record("999", TODAY, created_at=datetime(2026, 11, 10, 12, tzinfo=timezone.utc)),
            record("-10"), record("NaN"),
        ])
        result = self.check("1500")
        self.assertEqual((result.sample_count, result.baseline_amount), (5, 200))
        self.repo.expenses.assert_called_once_with(
            OWNER, "PKR", start=None, end=date(2026, 11, 11), category="Food",
        )

    def test_saved_candidate_exclusion_and_equal_date_order_are_reproducible(self):
        instant = datetime(2026, 11, 5, 9, tzinfo=timezone.utc)
        saved = record("1800", date(2026, 11, 5), id=UUID(int=10), created_at=instant)
        prior = replace(saved, id=UUID(int=9), amount=Decimal("300"))
        after = replace(saved, id=UUID(int=11), amount=Decimal("9500"))
        late_insert = record("9500", date(2026, 11, 4), created_at=REFERENCE)
        self.repo.expenses.return_value = [saved, after, prior, prior, late_insert] + [
            record("200") for _ in range(4)
        ]
        result = self.check("1800", day=saved.transaction_date, saved=saved)
        self.repo.expenses.return_value.reverse()
        self.assertEqual(self.check("1800", day=saved.transaction_date, saved=saved), result)
        self.assertEqual((result.expense_id, result.sample_count, result.baseline_amount), (saved.id, 5, 200))

    def test_backdated_draft_excludes_same_day_and_later_expenses(self):
        self.repo.expenses.return_value.extend([
            record("300", date(2026, 11, 5)), record("300", date(2026, 11, 6)),
        ])
        self.assertEqual(self.check("1500", day=date(2026, 11, 5)).sample_count, 5)

    def test_conflicting_duplicate_ids_are_omitted_instead_of_counted_twice(self):
        one = record("20")
        self.repo.expenses.return_value = [one, one, replace(one, amount=Decimal("20000"))]
        self.assertEqual(self.check("1500").sample_count, 0)

    def test_zero_baseline_and_extreme_outlier_safeguards(self):
        self.repo.expenses.return_value = [record("0") for _ in range(5)]
        zero = self.check("2500")
        self.assertEqual((zero.status, zero.baseline_amount, zero.is_unusual), ("unavailable_baseline", 0, False))
        self.repo.expenses.return_value = [record("200") for _ in range(4)] + [record("1E+150")]
        self.assertTrue(self.check("1500").is_unusual)
        self.assertFalse(self.check("1500", policy=AnomalyPolicy(baseline_method="mean")).is_unusual)

    def test_configurable_thresholds_are_strict_and_never_invoke_gemini(self):
        self.repo.expenses.return_value = [record("100"), record("100")]
        policy = AnomalyPolicy(minimum_history=2, threshold_multiplier="2", minimum_amount="300")
        with patch("backend.app.services.ai_service.GeminiExpenseProvider.extract") as gemini:
            self.assertFalse(self.check("200", policy=policy).is_unusual)
            self.assertFalse(self.check("300", policy=policy).is_unusual)
            self.assertTrue(self.check("300.01", policy=policy).is_unusual)
            gemini.assert_not_called()

    def test_invalid_candidate_identity_currency_amount_and_category_are_rejected(self):
        data = {"amount": "1500", "category": "Food", "transaction_date": TODAY}
        for fields in ({"amount": "-1"}, {"amount": "0"}, {"amount": 1.5},
                       {"amount": "Infinity"}, {"category": " "}, {"user_id": OWNER}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                AnomalyCandidate.model_validate({**data, **fields})
        with self.assertRaises(ValueError):
            self.service.check_anomaly(
                AnomalyCandidate.model_validate({**data, "currency": "USD"}),
                reference_datetime=REFERENCE,
            )
        with self.assertRaises(ValueError):
            self.check("1500", saved=record("1500", TODAY, user_id=OTHER_USER))
        with self.assertRaises(ValueError):
            self.check("1500", day=date(2026, 11, 11))
        with self.assertRaises(TypeError):
            SpendingAnalyticsService(self.repo, str(OWNER))
        self.repo.expenses.assert_not_called()
