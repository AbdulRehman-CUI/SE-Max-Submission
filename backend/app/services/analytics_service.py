from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
import pytz
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Budget, Expense


HISTORICAL_MONTH_COUNT = 3
CATEGORY_ANOMALY_MIN_INCREASE = Decimal("1.5")
CATEGORY_HIGH_INCREASE_PERCENT = Decimal("100")
CATEGORY_CRITICAL_INCREASE_PERCENT = Decimal("200")
MIN_HISTORICAL_TRANSACTIONS = 10
LARGE_TRANSACTION_MULTIPLIER = Decimal("3")
CRITICAL_TRANSACTION_MULTIPLIER = Decimal("5")


class AnalyticsService:

    @staticmethod
    def _get_current_karachi_date() -> date:
        tz = pytz.timezone(settings.LOCAL_TIMEZONE)
        return datetime.now(tz).date()

    @staticmethod
    def get_summary(user_id: uuid.UUID, db: Session) -> Dict[str, Any]:
        today = AnalyticsService._get_current_karachi_date()
        cur_year, cur_month = today.year, today.month

        if cur_month == 1:
            prev_year, prev_month = cur_year - 1, 12
        else:
            prev_year, prev_month = cur_year, cur_month - 1

        _, last_day_cur = calendar.monthrange(cur_year, cur_month)
        start_cur = date(cur_year, cur_month, 1)
        end_cur = date(cur_year, cur_month, last_day_cur)

        _, last_day_prev = calendar.monthrange(prev_year, prev_month)
        start_prev = date(prev_year, prev_month, 1)
        end_prev = date(prev_year, prev_month, last_day_prev)

        all_expenses = db.query(Expense.amount).filter(Expense.user_id == user_id).all()
        total_transactions = len(all_expenses)
        total_spent = sum((Decimal(str(e[0])) for e in all_expenses), Decimal("0.00"))
        average_transaction = (
            round(total_spent / Decimal(total_transactions), 2)
            if total_transactions > 0
            else Decimal("0.00")
        )

        cur_expenses = (
            db.query(Expense.amount)
            .filter(
                Expense.user_id == user_id,
                Expense.transaction_date >= start_cur,
                Expense.transaction_date <= end_cur,
            )
            .all()
        )
        current_month_spending = sum((Decimal(str(e[0])) for e in cur_expenses), Decimal("0.00"))

        prev_expenses = (
            db.query(Expense.amount)
            .filter(
                Expense.user_id == user_id,
                Expense.transaction_date >= start_prev,
                Expense.transaction_date <= end_prev,
            )
            .all()
        )
        previous_month_spending = sum((Decimal(str(e[0])) for e in prev_expenses), Decimal("0.00"))

        if previous_month_spending == Decimal("0.00"):
            if current_month_spending > Decimal("0.00"):
                spending_change_percentage = Decimal("100.00")
            else:
                spending_change_percentage = Decimal("0.00")
        else:
            change = (current_month_spending - previous_month_spending) / previous_month_spending
            spending_change_percentage = round(change * Decimal("100"), 2)

        return {
            "total_spent": total_spent,
            "total_transactions": total_transactions,
            "average_transaction": average_transaction,
            "current_month_spending": current_month_spending,
            "previous_month_spending": previous_month_spending,
            "spending_change_percentage": spending_change_percentage,
        }

    @staticmethod
    def get_categories(user_id: uuid.UUID, db: Session) -> List[Dict[str, Any]]:
        user_expenses = db.query(Expense.category, Expense.amount).filter(Expense.user_id == user_id).all()
        total_spent = sum((Decimal(str(e[1])) for e in user_expenses), Decimal("0.00"))

        cat_map: Dict[str, Dict[str, Any]] = {}
        for cat, amt in user_expenses:
            amt_dec = Decimal(str(amt))
            if cat not in cat_map:
                cat_map[cat] = {"category": cat, "total_spent": Decimal("0.00"), "transaction_count": 0}
            cat_map[cat]["total_spent"] += amt_dec
            cat_map[cat]["transaction_count"] += 1

        result: List[Dict[str, Any]] = []
        for cat_data in cat_map.values():
            if total_spent > Decimal("0.00"):
                pct = round((cat_data["total_spent"] / total_spent) * Decimal("100"), 2)
            else:
                pct = Decimal("0.00")
            result.append({
                "category": cat_data["category"],
                "total_spent": cat_data["total_spent"],
                "transaction_count": cat_data["transaction_count"],
                "percentage_of_total": pct,
            })

        result.sort(key=lambda x: x["total_spent"], reverse=True)
        return result

    @staticmethod
    def get_monthly(user_id: uuid.UUID, db: Session, year: Optional[int] = None) -> List[Dict[str, Any]]:
        expenses = db.query(Expense.transaction_date, Expense.amount).filter(Expense.user_id == user_id).all()

        monthly_map: Dict[tuple[int, int], Dict[str, Any]] = {}
        for t_date, amt in expenses:
            y = t_date.year
            m = t_date.month
            if year is not None and y != year:
                continue
            key = (y, m)
            if key not in monthly_map:
                monthly_map[key] = {
                    "year": y,
                    "month": m,
                    "total_spent": Decimal("0.00"),
                    "transaction_count": 0,
                }
            monthly_map[key]["total_spent"] += Decimal(str(amt))
            monthly_map[key]["transaction_count"] += 1

        result = list(monthly_map.values())
        result.sort(key=lambda x: (x["year"], x["month"]), reverse=True)
        return result

    @staticmethod
    def get_budget_status(
        user_id: uuid.UUID,
        db: Session,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        today = AnalyticsService._get_current_karachi_date()
        target_year = year if year is not None else today.year
        target_month = month if month is not None else today.month

        budgets = (
            db.query(Budget)
            .filter(
                Budget.user_id == user_id,
                Budget.year == target_year,
                Budget.month == target_month,
            )
            .all()
        )

        _, last_day = calendar.monthrange(target_year, target_month)
        start_date = date(target_year, target_month, 1)
        end_date = date(target_year, target_month, last_day)

        expenses = (
            db.query(Expense.category, Expense.amount)
            .filter(
                Expense.user_id == user_id,
                Expense.transaction_date >= start_date,
                Expense.transaction_date <= end_date,
            )
            .all()
        )

        spent_by_category: Dict[str, Decimal] = {}
        for cat, amt in expenses:
            spent_by_category[cat] = spent_by_category.get(cat, Decimal("0.00")) + Decimal(str(amt))

        result: List[Dict[str, Any]] = []
        for b in budgets:
            limit_dec = Decimal(str(b.budget_limit))
            total_spent = spent_by_category.get(b.category, Decimal("0.00"))
            remaining_budget = limit_dec - total_spent
            if limit_dec > Decimal("0.00"):
                utilization = round((total_spent / limit_dec) * Decimal("100"), 2)
            else:
                utilization = Decimal("0.00")

            result.append({
                "category": b.category,
                "budget_limit": limit_dec,
                "total_spent": total_spent,
                "remaining_budget": remaining_budget,
                "utilization_percentage": utilization,
            })

        return result

    @staticmethod
    def detect_anomalies(user_id: uuid.UUID, db: Session) -> Dict[str, Any]:
        karachi_tz = pytz.timezone("Asia/Karachi")
        now = datetime.now(karachi_tz)
        today = now.date()
        current_month_start = date(today.year, today.month, 1)

        historical_months = []
        for offset in range(1, HISTORICAL_MONTH_COUNT + 1):
            month = today.month - offset
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            historical_months.append((year, month))
        historical_month_set = set(historical_months)

        expenses = (
            db.query(
                Expense.id,
                Expense.category,
                Expense.amount,
                Expense.transaction_date,
            )
            .filter(Expense.user_id == user_id)
            .filter(Expense.transaction_date <= today)
            .order_by(Expense.transaction_date.asc(), Expense.id.asc())
            .all()
        )

        monthly_spending: Dict[str, Dict[tuple[int, int], Decimal]] = {}
        represented_months = set()
        historical_amounts: Dict[str, List[Decimal]] = {}
        current_spending: Dict[str, Decimal] = {}
        current_expenses = []

        for expense_id, category, amount, transaction_date in expenses:
            amount_dec = Decimal(str(amount))
            month_key = (transaction_date.year, transaction_date.month)

            if month_key in historical_month_set:
                represented_months.add(month_key)
                category_months = monthly_spending.setdefault(category, {})
                category_months[month_key] = (
                    category_months.get(month_key, Decimal("0.00")) + amount_dec
                )

            if transaction_date < current_month_start:
                historical_amounts.setdefault(category, []).append(amount_dec)
            else:
                current_expenses.append((expense_id, category, amount_dec, transaction_date))
                current_spending[category] = (
                    current_spending.get(category, Decimal("0.00")) + amount_dec
                )

        anomalies: List[Dict[str, Any]] = []
        detected_at = now

        if represented_months == historical_month_set:
            for category in sorted(current_spending):
                category_months = monthly_spending.get(category, {})
                historical_average = sum(
                    (
                        category_months.get(month, Decimal("0.00"))
                        for month in historical_months
                    ),
                    Decimal("0.00"),
                ) / Decimal(HISTORICAL_MONTH_COUNT)

                if historical_average <= Decimal("0.00"):
                    continue

                spending = current_spending[category]
                if spending < historical_average * CATEGORY_ANOMALY_MIN_INCREASE:
                    continue

                increase_percentage = (
                    (spending - historical_average)
                    / historical_average
                    * Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if increase_percentage >= CATEGORY_CRITICAL_INCREASE_PERCENT:
                    severity = "critical"
                elif increase_percentage >= CATEGORY_HIGH_INCREASE_PERCENT:
                    severity = "high"
                else:
                    severity = "medium"

                anomalies.append({
                    "category": category,
                    "historical_average": historical_average.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "current_spending": spending,
                    "increase_percentage": increase_percentage,
                    "severity": severity,
                    "anomaly_type": "category_spending_increase",
                    "detected_at": detected_at,
                })

        historical_medians = {}
        for category, amounts in historical_amounts.items():
            if len(amounts) < MIN_HISTORICAL_TRANSACTIONS:
                continue
            sorted_amounts = sorted(amounts)
            middle = len(sorted_amounts) // 2
            if len(sorted_amounts) % 2:
                historical_medians[category] = sorted_amounts[middle]
            else:
                historical_medians[category] = (
                    sorted_amounts[middle - 1] + sorted_amounts[middle]
                ) / Decimal("2")

        for expense_id, category, amount, transaction_date in current_expenses:
            historical_median = historical_medians.get(category)
            if historical_median is None:
                continue

            threshold = historical_median * LARGE_TRANSACTION_MULTIPLIER
            if amount <= threshold:
                continue

            anomalies.append({
                "expense_id": str(expense_id),
                "category": category,
                "amount": amount,
                "historical_median": historical_median,
                "threshold_amount": threshold,
                "severity": (
                    "critical"
                    if amount >= historical_median * CRITICAL_TRANSACTION_MULTIPLIER
                    else "high"
                ),
                "anomaly_type": "large_individual_transaction",
                "transaction_date": transaction_date,
                "detected_at": detected_at,
            })

        return {
            "user_id": user_id,
            "anomalies": anomalies,
            "total_anomalies": len(anomalies),
        }

    @staticmethod
    def get_financial_insights(user_id: uuid.UUID, db: Session) -> Dict[str, Any]:
        categories = AnalyticsService.get_categories(user_id, db)
        insights = []
        if categories:
            top_category = categories[0]
            insights.append(
                f"Your highest spending category is {top_category['category']} with {top_category['total_spent']} spent."
            )
        else:
            insights.append("No expenses recorded yet. Start logging expenses to see insights.")

        return {
            "user_id": user_id,
            "insights": insights,
        }
