# Frontend and backend integration

The local checkout contains the finance backend and test fixtures. Frontend source, its framework, and the production authentication contract are pending from the team. Use this guide to connect the frontend after Developer 1 mounts the approved routers. Paths below are relative to the shared API base. `/api` was used in tests as an example prefix. The five analytics paths and the additive SMS metadata remain provisional.

## Authentication and configuration

Use the foundation's actual registration and login routes once available. Read its token response and send `Authorization: Bearer <access_token>` with every finance request. Handle a `401` through the frontend's existing authentication flow. Set the frontend's public API base URL to the deployed backend origin and approved prefix. A framework-specific variable name, browser origin allowlist, and token lifecycle depend on the missing frontend and backend configuration. Set `GEMINI_API_KEY` and optional `GEMINI_MODEL` on the server only. Use Developer 1's actual JWT and PostgreSQL environment variables.

## API operations

| Method and path | Request | Success |
| --- | --- | --- |
| `POST /expenses` | `ExpenseCreate` | `201 ExpenseResponse` |
| `GET /expenses` | Optional `skip`, `limit` | `200 ExpenseResponse[]` |
| `GET /expenses/{expense_id}` | Expense UUID | `200 ExpenseResponse` |
| `PATCH /expenses/{expense_id}` | Supplied fields from `ExpenseCreate` | `200 ExpenseResponse` |
| `DELETE /expenses/{expense_id}` | Expense UUID | `204` with an empty body |
| `POST /budgets` | `BudgetCreate` | `201 BudgetResponse` |
| `GET /budgets` | Optional `skip`, `limit` | `200 BudgetResponse[]` |
| `GET /budgets/{budget_id}` | Budget UUID | `200 BudgetResponse` |
| `PATCH /budgets/{budget_id}` | Supplied fields from `BudgetCreate` | `200 BudgetResponse` |
| `DELETE /budgets/{budget_id}` | Budget UUID | `204` with an empty body |
| `GET /budgets/{budget_id}/summary` | Budget UUID | `200 BudgetSummary` |
| `POST /expenses/parse` | `{"text":"..."}` | `200 ExpenseParseResponse` |
| `POST /expenses/parse-sms` | `{"text":"..."}` | `200 SMSParseResponse` |
| `GET /analytics/monthly` | Required `year`, `month` | `200 MonthlySpendingSummary` |
| `GET /analytics/categories` | Required `year`, `month` | `200 CategorySpending[]` |
| `GET /analytics/trends` | Optional `months` (default `3`), `end_month` (`YYYY-MM-DD`) | `200 MonthlySpendingTrend[]` |
| `POST /analytics/anomalies/check` | `AnomalyCheckRequest` | `200 AnomalyResult` |
| `GET /analytics/insights` | Required `year`, `month` | `200 FinancialInsightsResponse` |

`ExpenseCreate` requires `amount`, `category`, and `transaction_date`. `currency` defaults to `PKR`, and `description` and `payment_method` are optional. `ExpenseResponse` adds `id`, `user_id`, and `created_at`. `BudgetCreate` requires `budget_limit`, `category`, `year`, and `month`. `BudgetResponse` adds `id`, `user_id`, `created_at`, `total_spent`, and `remaining_budget`. `BudgetSummary` uses `budget_id`, `category`, `year`, `month`, `budget_limit`, `total_spent`, and `remaining_budget`. Preserve negative remainders. Pagination defaults to `skip=0` and `limit=20`, with `limit` capped at 100. Keep monetary values and percentages as decimal strings. PATCH omission preserves the field, and explicit null clears an expense description or payment method. The budget provider can lock period changes.

```sh
curl "$API_BASE/expenses?skip=0&limit=20" -H "Authorization: Bearer $ACCESS_TOKEN"
curl -X PATCH "$API_BASE/budgets/$BUDGET_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"budget_limit":"15000.00"}'
```

## Confirming a parsed expense

```sh
curl -X POST "$API_BASE/expenses/parse" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Paid PKR 500.00 for lunch on 2026-11-10."}'
```

The response includes `extracted_fields`, `missing_fields`, and `confirmation_required: true`. Render the draft for editing and fill missing fields. For SMS use the same body on `/expenses/parse-sms`. The response also provides `transaction_type`, `transaction_status`, `amount`, `currency`, `transaction_date`, `merchant`, `transaction_reference`, `source`, `is_expense_candidate`, and `clarification_required`. Show classifications without a save action when `is_expense_candidate` is false. When true, require the user to resolve clarification and confirm before posting the reviewed Expense fields. Treat references and SMS text as sensitive. Render category and description values as text.

```sh
curl -X POST "$API_BASE/expenses" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"amount":"500.00","currency":"PKR","category":"Food","description":"lunch","transaction_date":"2026-11-10"}'
```

## Analytics and insights

`MonthlySpendingSummary` contains `year`, `month`, `currency`, `total_spent`, `transaction_count`, `average_expense`, `categories`, `is_partial`, and `through_date`. Each category row has `category`, `total_spent`, `transaction_count`, and `percentage_of_total`. A trend point adds `change_amount` and `change_percentage`. Show the partial period label and treat null as unavailable. Use the summary's category array or the standalone categories route.

`AnomalyCheckRequest` accepts the candidate `amount`, `category`, `transaction_date`, and `currency` (default `PKR`). The provisional HTTP amount accepts up to 512 digits and 128 fractional places to bound arithmetic. The response includes `status`, `is_unusual`, `has_enough_history`, `sample_count`, `minimum_history`, `baseline_method`, `baseline_amount`, `threshold_amount`, `threshold_multiplier`, `minimum_amount`, `explanation`, and the candidate context fields. Show the server's explanation when history is insufficient or the baseline is unavailable. The check makes no expense entry.

```sh
curl "$API_BASE/analytics/trends?months=3&end_month=2026-11-01" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
curl "$API_BASE/analytics/insights?year=2026&month=11" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

A deterministic response for an empty partial month includes the empty-state summary and fallback indicator.

```json
{
  "summary": "Recorded spending for 2026-11 through 2026-11-10 is PKR 0. There are no recorded expenses in this period.",
  "insights": [
    {"type":"trend","title":"Monthly change","message":"There is no prior-month spending baseline for a percentage comparison.","severity":"info"},
    {"type":"budget","title":"Monthly budgets","message":"No budgets are available for this period.","severity":"info"},
    {"type":"awareness","title":"Spending awareness","message":"Record an expense to start building a spending summary.","severity":"info"}
  ],
  "warnings": [],
  "period": {"year":2026,"month":11,"through_date":"2026-11-10","is_partial":true},
  "currency": "PKR",
  "generated_by": "deterministic",
  "is_fallback": true
}
```

Render `warnings` independently of the ranked `insights`. A valid Gemini ranking uses `generated_by: "gemini"` and `is_fallback: false`. Provider fallback is a normal `200` response. Show the data and its source.

## Error handling and demo sequence

The fixture app uses FastAPI's `detail` body. `401` indicates authentication failure, `404` covers both missing and unowned finance resources, `409` is a duplicate budget, and `422` covers validation and disabled period edits. Expense parsing can return `502`, `503`, or `504`. Unbound providers return `503` and unexpected service failures follow the shared server error handler. Confirm Developer 1's final error envelope before wiring UI messages.

For an integrated demo, sign in with an isolated test account, create and edit an expense, list it, and update a budget against its spending. Parse a synthetic text expense and confirm it. Parse a balance or credit SMS and show its classification. Open monthly analytics, categories, trends, the anomaly check, and insights. Run the insights view with the shared adapter and with the deterministic provider configuration. Delete the test expense and confirm that the budget and analytics totals change. The in-process tests currently verify the backend contracts with fixtures, and the browser workflow remains pending.
