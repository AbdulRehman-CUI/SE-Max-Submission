# Spending analytics and deterministic anomaly checks

**PROPOSED — REQUIRES TEAM APPROVAL.** Developer 1 owns production analytics and anomaly routes. The available local refs contain no Developer 1 analytics implementation. Phase 7 provides `SpendingAnalyticsService`, its response schemas, and a read-only repository adapter for Developer 1's review. The service uses the shared Expense interface and a UUID supplied by authentication. It opens no session or connection itself and has no Gemini dependency.

## Monthly reporting

Every report uses exactly one currency. The provisional default is PKR. The composition layer can select another currency explicitly. There is no exchange-rate conversion. Budget totals remain PKR-only pending team approval.

`transaction_date` is an Asia/Karachi calendar date. A closed month's query uses `[month_start, next_month_start)`, including the December-to-January transition. The current month includes dates through the current local date and returns `is_partial: true` and `through_date`. Tests can inject an aware reference datetime. Reports reject future periods. Budget summaries continue to use the full stored month, which can differ from an as-of analytics report if there are future-dated expense records.

- `total_spent` is the sum of matching expenses and `transaction_count` counts their rows. `average_expense` is total divided by count. An empty month has total and count zero, no category rows, and a null average.
- Each category row has its subtotal, transaction count, and `percentage_of_total`. The service allocates hundredths of a percent by largest remainder with ties broken by category order. Positive monthly totals therefore reconcile to exactly `100.00%`. All shares are zero when the total is zero. An uncategorized legacy row appears under a null category.
- Trends return one to 120 consecutive months in oldest-to-newest order. The default is three months ending in the current local month. An explicit `end_month` can select an earlier trailing window. Missing months are represented by zero totals. Each point includes its monthly category breakdown, absolute change from the previous point, and the percentage change rounded to two decimal places with half-even rounding. The first point has null changes. Percentage change is null when the previous total is zero. Treat changes marked `is_partial` as comparisons with an incomplete month.

Money and percentages serialize as Decimal strings. Totals and differences retain the source precision. Division for averages and mean baselines uses a half-even Decimal context sized for the input values, with at least 34 significant digits. Recurring quotients are rounded at that precision. Negative or non-finite stored amounts are ignored. Valid legacy zero rows are counted and contribute zero.

## Unusual spending

`check_anomaly` compares a validated candidate against qualifying history for the same authenticated owner, category, and currency. `AnomalyPolicy` defaults to the median of at least **5** prior expenses, a multiplier of **3**, and an absolute minimum of **PKR 1,000**. The caller can set a different history minimum, multiplier, absolute amount, or `baseline_method="mean"`. When configuring another currency, supply an absolute minimum appropriate to that currency. The candidate must strictly exceed both `baseline × multiplier` and the absolute minimum to be flagged. For a mean baseline the comparison uses `candidate × count > history_sum × multiplier` so a rounded mean cannot change the decision.

The service returns `insufficient_history` with the sample count and required minimum when there are too few rows. A zero baseline returns `unavailable_baseline` with no alert. With a positive baseline and enough history, the result is `normal` or `unusual`. The result includes the baseline, amount, multiplier, threshold, sample count, and a deterministic explanation. A spending alert is a prompt to review the transaction. Large one-off expenses can still trigger it.

For a saved candidate, pass a trusted `SpendingRecord` built from the server's owner-scoped expense lookup. The service excludes the candidate ID and orders equal dates by aware `created_at`, then UUID. It excludes later transaction dates and any records created after the saved candidate. An unsaved current-day candidate uses already-recorded history through the reference time. A backdated draft uses strictly earlier transaction dates because it has no reliable position within its own day. Identical duplicate records count once. Conflicting copies of one ID are omitted. Blank categories and invalid candidate amounts fail validation. Anomaly checks read history without saving the candidate or invoking Gemini.

## Mid-month budget limits

The existing PATCH route re-reads the same budget's full-month total after a limit-only update. Prior spending stays included and a reduced limit can produce a negative remainder. The provider can lock explicit period edits with `allow_period_changes=False`, while the default preserves the existing PATCH contract. The [budget guide](BUDGET_MODULE.md#budget-changes-during-the-month) describes approval status, uniqueness, and historical behavior.

## Proposed API and ownership

| Route | Inputs | Response |
| --- | --- | --- |
| `GET /analytics/monthly` | `year`, `month` | `MonthlySpendingSummary` |
| `GET /analytics/categories` | `year`, `month` | The monthly summary's `list[CategorySpending]` |
| `GET /analytics/trends` | Optional `months` and final month | `list[MonthlySpendingTrend]` |
| `POST /analytics/anomalies/check` | `AnomalyCheckRequest` with `amount`, `category`, `transaction_date`, `currency` | `AnomalyResult` |
| `GET /analytics/insights` | `year`, `month` | `FinancialInsightsResponse` |

Phase 8 exports `app.routes.provisional_analytics.router` for explicit registration after Developer 1's review. The integrated app must supply the real authenticated user and request session through the project's existing dependencies. See the [registration example](AI_FINANCIAL_INSIGHTS.md#integration). The analytics provider uses the proposed imports below.

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from .database import get_db
from .models import Expense, User
from .routes.auth import get_current_user
from .services.spending_analytics_service import (
    SpendingAnalyticsService,
    SQLAlchemySpendingRepository,
)


def provide_spending_analytics(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SpendingAnalyticsService:
    return SpendingAnalyticsService(SQLAlchemySpendingRepository(db, Expense), user.id)
```

Use the dependency in Developer 1's handlers and call `monthly(year, month)`, `monthly(year, month).categories`, `trends(months, end_month=...)`, or `check_anomaly(candidate)`. If the approved API accepts an expense ID for a saved check, retrieve it through the shared owner-scoped Expense lookup and pass the server-built record as `saved`. Map invalid periods and candidate input to the existing validation error format. The request schema forbids client-supplied ownership fields. The repository filters owner, currency, and dates with bound SQL predicates, and the service applies the same scope before aggregation.

The adapter projects the needed Expense fields in a single scoped query for a monthly summary, a full trend window, or an anomaly history read. It aggregates those facts in Python. Before production use on large datasets, validate PostgreSQL indexes and query plans and consider grouped monthly totals behind the shared repository. Review whether Developer 1 already has an approved analytics schema, aggregate query, or anomaly policy before wiring this provisional version. The existing shared model, JWT dependency, and transaction policy remain integration prerequisites.

## Verification

Run `python -m unittest discover -s backend/tests -v` with the existing test dependencies, or `bash scripts/test.sh`. Analytics tests use fixture repositories and compile the adapter's SQL. Budget regression tests check the generated writes and live aggregate reads. An isolated embedded PostgreSQL runtime also exercised the generated budget SQL on synthetic rows. Neither check validates the production database, ORM mappings, or JWT integration. Phase 8 can consume the calculated statistics after Developer 1 confirms these contracts.
