# SpendSense backend merge integration

The active merge combines `main` at `0006ed6` with `origin/feature/backend` at `4894a61`. The conflicted paths were the expense and budget routers and the AI service. This file records the integrated contract. The Phase 1–8 documents also contain historical proposals and test results.

| Files | Integration change |
| --- | --- |
| `backend/app/routes/expenses.py`, `backend/app/routes/budgets.py` | Both `PUT` and `PATCH` perform the existing partial update through the same owner-scoped service. The expense parser paths remain static POST operations. The HTTP write paths reject values outside `NUMERIC(12,2)` before a write. |
| `backend/app/schemas.py` | Expense and budget responses retain `id` and expose the incoming `expense_id` and `budget_id` aliases. Finance write schemas enforce the actual text column lengths. Draft and analytics arithmetic can still retain higher Decimal precision before persistence. |
| `backend/app/models.py`, `backend/app/services/budget_service.py` | The shared Budget model accepts zero limits and years `1` through `9999`. The duplicate handler recognizes the incoming `uq_budget_user_category_month_year` constraint and the earlier proposed spelling. |
| `backend/app/main.py` | Production uses the incoming `get_db`, ORM models, and `get_current_user` to bind all finance providers. The synchronous request dependency owns session closure and finance services own commit and rollback. The app mounts legacy analytics at `/analytics` and the newer contracts at `/v2/analytics`. |
| `backend/app/services/ai_service.py`, `backend/app/config.py`, `backend/.env.example` | The lifespan shares one Google Gen AI SDK adapter across text parsing, SMS enrichment, and insights. Model, timeout, and key come from the shared settings. Parsing produces drafts and requires configured Gemini. Insights can return deterministic output without a provider. The environment example uses placeholders. |
| `backend/app/routes/analytics.py`, `backend/app/routes/provisional_analytics.py`, `backend/app/services/analytics_service.py` | Legacy insight requests retain `user_id`, `insights`, `generated_at`, and `status`, using the current month and the same grounded generator as v2. Legacy analytics use PKR consistently and budget status reuses the live budget aggregate. The legacy summary marks the current month partial and returns null percentage change when the prior month has zero spending. The legacy anomaly listing retains both original rules. |
| `backend/requirements.txt`, `scripts/test.sh` | The backend dependency file includes Google Gen AI and timezone data. CI installs from that shared file. |
| `backend/tests/test_finance_integration.py`, `backend/tests/test_provisional_analytics.py`, `backend/tests/test_merged_app.py`, `backend/tests/test_merged_postgres.py` | Tests cover merged routing and mapper contracts, the real JWT dependency with mocked sessions, and an opt-in disposable native PostgreSQL run. |
| `docs/FRONTEND_BACKEND_INTEGRATION.md`, `docs/MERGE_INTEGRATION.md` | The frontend guide reflects the integrated paths and this document records the merge decisions. |
| Incoming package initializers, `backend/.gitignore`, `backend/app/database.py` | Trimmed trailing blank lines flagged by the staged whitespace check. |

Expense and budget lists use `skip` and `limit`, defaulting to the first 20 results. Missing and non-owned records return `404`. Duplicate monthly budgets return `409`. Money accepted for persistence fits ten integer digits and two fractional places. The service accepts trailing zeros that do not change the value. A requested update can clear optional expense text fields with null. Required fields must remain non-null.

## Existing databases

The updated ORM constraints apply when creating a fresh schema. For an existing database using the incoming constraint names, review and apply the following through the deployment's migration process before enabling the updated budget writes.

```sql
ALTER TABLE budgets DROP CONSTRAINT ck_budget_limit_positive;
ALTER TABLE budgets ADD CONSTRAINT ck_budget_limit_nonnegative CHECK (budget_limit >= 0);
ALTER TABLE budgets DROP CONSTRAINT ck_budget_year_range;
ALTER TABLE budgets ADD CONSTRAINT ck_budget_year_range CHECK (year >= 1 AND year <= 9999);
```

The incoming monthly uniqueness key stays in place. Verify the actual database constraints before applying the migration. The shared `NUMERIC(12,2)` column types stay in place.

## Test and run commands

Install the backend dependencies and run `python -m unittest discover -s backend/tests -v` from the repository root. For the native PostgreSQL integration test, create a fresh empty loopback database whose name starts with `spendsense_merge_test`, set `SPENDSENSE_TEST_POSTGRES_URL` to its `postgresql+psycopg` URL, and run this module in a fresh process.

```sh
python -m unittest backend.tests.test_merged_postgres -v
```

The test creates schema and synthetic records in the specified empty database. Use a disposable cluster. The standard suite skips this opt-in test and the live Gemini smoke test. To run the application, configure `backend/.env` from its example, then run `uvicorn app.main:app` from `backend`.

The regression run with real ORM mapper checks enabled recorded 128 passed, 0 failed, and 2 opt-in skips. Compilation and OpenAPI generation passed for 31 unique operations. A separate test on disposable native PostgreSQL 18.6 passed registration, login, owner-scoped finance operations, duplicate budget rollback, December-to-January totals, and live totals after expense updates and deletion. Mocked Gemini tests covered the shared provider and parsing behavior. Live Gemini and deployment integration remain unverified.
