# SpendSense backend contract

## Status

The Phase 1 brief confirms the entity names and field names below, UUID identifiers, Decimal money, PKR as the expense currency default, Asia/Karachi for local periods and relative dates, UTC for stored timestamps where appropriate, and Gemini as the primary AI provider. The target backend stack is FastAPI, PostgreSQL, SQLAlchemy, and Pydantic v2.

**PROPOSED — REQUIRES TEAM APPROVAL** applies to the schema constraints, database mappings, API shapes, endpoint behavior, and service signatures introduced here. The Developer 2 checkout has no SQLAlchemy models, database session provider, authentication dependency, or routers to verify against. The tables separate the agreed field names from the proposed mappings.

## Shared entities

| Entity | Confirmed field names | Proposed Python / PostgreSQL type | Proposed nullable |
| --- | --- | --- | --- |
| `User` | `id` | `UUID` / `uuid` primary key | No |
| `User` | `username`, `email`, `hashed_password` | `str` / text or varchar | No |
| `User` | `created_at` | Aware `datetime` / `timestamptz` | No |
| `Expense` | `id`, `user_id` | `UUID` / `uuid`, with `id` the primary key and `user_id` referencing `User.id` | No |
| `Expense` | `amount` | `Decimal` / `numeric` | No |
| `Expense` | `category`, `currency` | `str` / text or varchar | No |
| `Expense` | `description`, `payment_method` | `str` / text or varchar | Yes |
| `Expense` | `transaction_date` | `date` / `date` | No |
| `Expense` | `created_at` | Aware `datetime` / `timestamptz` | No |
| `Budget` | `id`, `user_id` | `UUID` / `uuid`, with `id` the primary key and `user_id` referencing `User.id` | No |
| `Budget` | `category` | `str` / text or varchar | No |
| `Budget` | `budget_limit` | `Decimal` / `numeric` | No |
| `Budget` | `month`, `year` | `int` / integer | No |
| `Budget` | `created_at` | Aware `datetime` / `timestamptz` | No |

Use `id` and `user_id` in persisted response objects. The proposed path parameters are `expense_id` and `budget_id`, which map to the corresponding entity's `id`. UUIDs use hyphenated strings in JSON. Developer 1 owns ID generation and database defaults. Password hashes belong to the authentication layer and must stay out of public responses.

### Money and dates

- Use Python `Decimal` for storage-bound values and future calculations. Clients should submit decimal strings such as `"1250.50"` to preserve precision. Exact JSON integers are also accepted. Fractional JSON numbers, booleans, and non-finite values fail validation. Monetary values serialize as JSON strings through Pydantic's JSON mode. [Pydantic Decimal documentation](https://docs.pydantic.dev/latest/api/standard_library_types/#decimals)
- The schemas apply sign rules without rounding. PostgreSQL precision and scale, supported currencies, and rounding rules remain open. Confirm a single budget currency or an explicit conversion policy before aggregating expenses across currencies.
- `transaction_date` is a calendar date in `YYYY-MM-DD`. Resolve relative dates against `Asia/Karachi`. Derive budget month and year in that timezone and use local calendar boundaries for matching expenses. `created_at` uses an aware datetime and should be written in UTC. The response serializes timestamps in ISO 8601 with an offset.

## Request and response schemas

| Schema | Proposed shape and behavior |
| --- | --- |
| `ExpenseCreate` | Requires `amount`, `category`, and `transaction_date`. `currency` defaults to `PKR`. `description` and `payment_method` may be omitted or null. |
| `ExpenseUpdate` | Accepts any subset of the create fields. An omitted field stays as stored. Explicit null clears `description` or `payment_method`. Other fields require a value when present. |
| `ExpenseResponse` | Validates ORM attributes. Includes `id`, `user_id`, `created_at`, and all expense fields, including nullable fields. |
| `BudgetCreate` | Requires `category`, `budget_limit`, `month`, and `year`. |
| `BudgetUpdate` | Accepts any subset of the create fields. Each supplied field requires a value. |
| `BudgetResponse` | Validates ORM attributes. Includes `id`, `user_id`, `created_at`, and all budget fields. `total_spent` and `remaining_budget` are optional service-supplied values and default to null. |
| `ExpenseParseRequest`, `SMSParseRequest` | Require `text`, either a natural-language expense or a pasted wallet or bank SMS. |
| `ExpenseParseResponse`, `SMSParseResponse` | Return `extracted_fields`, a draft with the six expense input fields. Unknown values stay null, including `currency`. `missing_fields` lists required `ExpenseCreate` fields absent from the draft. `confirmation_required` is always `true`. |

**PROPOSED — REQUIRES TEAM APPROVAL.** Phase 5 adds `transaction_type`, `transaction_status`, `amount`, `currency`, `transaction_date`, `merchant`, `transaction_reference`, `source`, `is_expense_candidate`, and `clarification_required` to `SMSParseResponse`. These fields describe the notification separately from the inherited draft. When `is_expense_candidate` is false, the inherited `extracted_fields` values are null. Clients check eligibility and clarification before offering confirmation. SMS metadata is parsing-only. See [SMS parsing](SMS_PARSING.md) for classifications, field semantics, and examples.

Validation trims strings and rejects blank values. Category and payment method are free text. Currency accepts three ASCII letters and normalizes them to uppercase. `amount` must be greater than zero and `budget_limit` must be at least zero. `month` and `year` require JSON integers in `1–12` and `1–9999`, respectively. Request models reject unknown fields, including client-supplied IDs and ownership. For PATCH, pass `model_dump(exclude_unset=True)` to the service so explicit nulls remain distinguishable from omissions. An empty patch is valid and leaves values as stored.

`total_spent` and `remaining_budget` are response data derived by the service. Once currency treatment is agreed, the proposed calculation sums the authenticated user's matching expenses for the budget category and local period, then computes `remaining_budget = budget_limit - total_spent`. A negative remainder represents overspending.

**PROPOSED — REQUIRES TEAM APPROVAL.** A budget limit applies to the whole stored calendar month. A limit-only PATCH preserves the period and recalculates the remaining amount from current expenses. Application composition can lock explicit period changes. See [mid-month budget behavior](BUDGET_MODULE.md#budget-changes-during-the-month).

**PROPOSED — REQUIRES TEAM APPROVAL.** Phase 7 adds provisional `MonthlySpendingSummary`, `CategorySpending`, `MonthlySpendingTrend`, `AnomalyCandidate`, and `AnomalyResult` schemas. Analytics reports one currency per request and marks current-month values as partial. Anomaly results distinguish insufficient history from normal spending. See [analytics and anomalies](ANALYTICS_AND_ANOMALIES.md) for the proposed endpoints and ownership boundaries.

**PROPOSED — REQUIRES TEAM APPROVAL.** Phase 8 exports an unmounted analytics router with monthly, category, trend, anomaly, and insight endpoints. `FinancialInsightsResponse` includes a server-rendered summary, ranked insights, warnings, period, currency, `generated_by`, and `is_fallback`. Gemini selects verified fact IDs. The server renders claims and falls back on expected provider failures. See [AI financial insights](AI_FINANCIAL_INSIGHTS.md) and the [frontend contract](FRONTEND_BACKEND_INTEGRATION.md).

## Authentication and user isolation

Expense and budget routes should depend on Developer 1's JWT-backed current-user dependency. Resolve `user_id` from the authenticated user returned by that dependency. Set it server-side on creates, scope list and aggregate queries to it, and include it alongside the resource ID in reads, updates, and deletes. Apply the same ownership rule to the expenses included in budget totals. The dependency's name, import path, return type, and UUID attribute are pending.

Reuse Developer 1's request-scoped session dependency, expected to be `get_db()` or its equivalent. Its import path, sync or async session type, lifecycle, and transaction ownership are pending. Both parsers require authentication and return drafts. The client reviews or corrects the result and then submits a separate `POST /expenses` request to save it.

## Proposed endpoints and errors

**PROPOSED — REQUIRES TEAM APPROVAL**. Paths are relative to the eventual API prefix. The proposed response bodies are schema objects or arrays, with a bodyless `204` on deletion. Adopt the backend's shared response and error conventions when they are established.

| Method and path | Request | Success | Route-specific errors |
| --- | --- | --- | --- |
| `POST /expenses` | `ExpenseCreate` | `201 ExpenseResponse` | `422` invalid body |
| `GET /expenses` | No body | `200 list[ExpenseResponse]` | List filters and pagination pending |
| `GET /expenses/{expense_id}` | UUID path parameter | `200 ExpenseResponse` | `404` missing or owned by another user, `422` invalid UUID |
| `PATCH /expenses/{expense_id}` | UUID path parameter and `ExpenseUpdate` | `200 ExpenseResponse` | `404` missing or owned by another user, `422` invalid UUID or body |
| `DELETE /expenses/{expense_id}` | UUID path parameter | `204` | `404` missing or owned by another user, `422` invalid UUID |
| `POST /budgets` | `BudgetCreate` | `201 BudgetResponse` | `422` invalid body, `409` duplicate under the approved uniqueness rule |
| `GET /budgets` | No body | `200 list[BudgetResponse]` | List filters and pagination pending |
| `GET /budgets/{budget_id}` | UUID path parameter | `200 BudgetResponse` | `404` missing or owned by another user, `422` invalid UUID |
| `PATCH /budgets/{budget_id}` | UUID path parameter and `BudgetUpdate` | `200 BudgetResponse` | `404` missing or owned by another user, `422` invalid UUID or body, `409` uniqueness conflict |
| `DELETE /budgets/{budget_id}` | UUID path parameter | `204` | `404` missing or owned by another user, `422` invalid UUID |
| `POST /expenses/parse` | `ExpenseParseRequest` | `200 ExpenseParseResponse` | `422` invalid body, `503` extraction provider unavailable |
| `POST /expenses/parse-sms` | `SMSParseRequest` | `200 SMSParseResponse`, including non-expense classifications | `422` invalid input or unsupported currency, `502` invalid provider output, `503` provider unavailable, `504` provider timeout |

All routes propose `401` for missing or invalid authentication, using Developer 1's eventual dependency behavior. Use the shared error formatter for validation and service errors. A successful extraction can return an incomplete draft with `missing_fields` populated.

## Future AI service interfaces

**PROPOSED — REQUIRES TEAM APPROVAL**. The functions below describe the future expense service boundary in `app/services/ai_service.py`. Confirm the shared Gemini client, sync or async calling convention, and provider error mapping with Developer 1 before implementing them.

```python
def parse_expense(request: ExpenseParseRequest) -> ExpenseParseResponse: ...
def parse_sms(request: SMSParseRequest) -> SMSParseResponse: ...
```

These interfaces receive validated text, return validated drafts, and leave persistence to the separate expense creation flow. Reuse the shared Gemini provider for any future provider calls.

## File ownership and integration

Paths in this section are relative to `backend/`.

| Owner | Files |
| --- | --- |
| Developer 1 | `app/main.py`, `app/database.py`, `app/models.py`, `app/config.py`, `app/utils/security.py`, `app/routes/auth.py`, `app/routes/analytics.py`, `app/services/analytics_service.py` |
| Developer 2 | `app/schemas.py`, `app/routes/expenses.py`, `app/routes/budgets.py`, `app/services/ai_service.py`, `app/services/expense_service.py`, `app/services/budget_service.py` |

Developer 1 owns router registration and supplies the ORM models, database dependency, and current-user dependency for Developer 2's routes to import. Agree on the shared Gemini entry point before writing either extraction flow.

## Before Phase 2

- [ ] Confirm final SQLAlchemy classes, import paths, field names, types, nullable constraints, ID generation, defaults, string lengths, and monetary precision and scale.
- [ ] Confirm `get_db()` import path, session type, lifecycle, and commit or rollback responsibility.
- [ ] Confirm the JWT current-user dependency, import path, return type, and UUID attribute.
- [ ] Confirm router prefixes, route registration, list response shape, HTTP statuses, and validation and error formats.
- [ ] Approve the budget uniqueness key, proposed as `(user_id, category, month, year)`, and the database constraint that enforces it.
- [ ] Confirm category and payment-method conventions, supported currencies, budget currency or conversion policy, and rounding rules.
- [ ] Confirm the shared Gemini provider owner, client import and interface, draft contract, and provider failure handling.
- [ ] Confirm `transaction_date`, UTC timestamp storage, Asia/Karachi period boundaries, the supported year range, and relative-date handling.
- [ ] Confirm PATCH nullability and no-op behavior, and approve the schema and test layout and backend dependency setup.

## Run the schema tests

From the repository root with Pydantic v2.9 or later in the v2 series installed, run `python -m unittest discover -s backend/tests -v`. The suite uses Python's standard library test runner and Pydantic.
