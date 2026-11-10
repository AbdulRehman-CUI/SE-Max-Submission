# AI financial insights

**Provisional, pending Developer 1 approval.** The analytics router collects the requested monthly trend, matching PKR budgets, and a deterministic check of the latest eligible recorded expense in the reporting period. `FinancialInsightsService` renders a spending summary, category concentration, month-over-month changes, budget use, and warnings from those computed values. The reporting clock and anomaly cutoff use Asia/Karachi. The Phase 7 anomaly policy decides whether to issue a warning.

## Grounding and privacy

The shared Gemini adapter receives bounded aggregate statistics with opaque fact IDs. Category labels, transaction and user IDs, raw expenses, SMS, credentials, and reference numbers stay outside the provider payload. Anomaly warnings are rendered from the local check. Gemini returns up to three distinct fact IDs to prioritize and selects one awareness topic from a fixed list. The schema rejects extra fields. The server checks that each selected ID was supplied and renders every statement, amount, percentage, and warning from its own data. Provider-authored claims and recommendations have no output field.

The response has `summary`, `insights`, `warnings`, `period`, `currency`, `generated_by`, and `is_fallback`. Insight and warning entries have `type`, `title`, `message`, and `severity`. `period` contains `year`, `month`, `through_date`, and `is_partial`. The service shows the top three categories and up to three budget utilization details. Exceeded budgets appear in `warnings` even when Gemini selects different facts. A zero budget has no utilization percentage. Budget totals cover the full stored month, while current-month analytics are partial through the local date. The latest-expense check is a snapshot of that expense's historical baseline.

## Deterministic fallback

Missing provider configuration, timeouts, rate limits, other expected provider failures, malformed JSON, invalid schemas, duplicate or unknown fact IDs, and unsupported claims all produce the same response shape. The server returns its own ordering with `generated_by: "deterministic"` and `is_fallback: true`. A valid selection returns `generated_by: "gemini"` and `is_fallback: false`. Empty expense history also uses the deterministic path. It supplies an empty-state summary, reports when budgets are absent, and leaves unavailable trend comparisons unquantified. Database failures and unexpected programming errors propagate to the application's normal error handler.

## Integration

Mount the exported provisional analytics router once after approval, or use its handlers in Developer 1's existing analytics router after checking for collisions. Reuse the existing `get_budget_service` override. Bind `get_spending_analytics` to the same current-user dependency and synchronous request session used for finance. Both providers must use the authenticated UUID. A mismatched budget owner fails the insights request before any provider call. Example imports use the provisional paths and should be adjusted to the actual foundation.

```python
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import Expense, User
from .routes.auth import get_current_user
from .routes.provisional_analytics import get_financial_insights, get_spending_analytics
from .routes.provisional_analytics import router as analytics_router
from .services.financial_insights_service import FinancialInsightsService
from .services.spending_analytics_service import SQLAlchemySpendingRepository, SpendingAnalyticsService


def provide_analytics(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SpendingAnalyticsService:
    return SpendingAnalyticsService(SQLAlchemySpendingRepository(db, Expense), user.id)


def provide_insights(request: Request) -> FinancialInsightsService:
    adapter = getattr(request.app.state, "gemini_adapter", None)
    return FinancialInsightsService(adapter)


app.dependency_overrides[get_spending_analytics] = provide_analytics
app.dependency_overrides[get_financial_insights] = provide_insights
app.include_router(analytics_router, prefix=api_prefix, dependencies=[Depends(get_current_user)])
```

During lifespan startup, set `app.state.gemini_adapter` to the same `GeminiExpenseProvider` instance used for expense and SMS parsing. Reuse the app's SDK client and `GEMINI_API_KEY` and `GEMINI_MODEL` configuration. If no shared adapter is available, the default insights service returns deterministic results. The existing adapter controls async execution, timeouts, and bounded retries. Database reads for insight inputs run in a synchronous FastAPI dependency before the async provider call.

## Verification

Run `python -m unittest discover -s backend/tests -v` with the existing test dependencies. The standard suite uses synthetic data and mocked HTTP. For an explicitly authorized live smoke test, configure the real key in the process environment and set `SPENDSENSE_LIVE_GEMINI=1`. Run the smoke test with this command.

```sh
python -m unittest backend.tests.test_financial_insights.LiveGeminiInsightsSmokeTest -v
```

The live check sends synthetic aggregate statistics, validates the grounded selection, and reports the model and outcome without printing the credential. It skips by default. See [frontend contract](FRONTEND_BACKEND_INTEGRATION.md) for the HTTP response examples.
