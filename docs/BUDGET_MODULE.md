# SpendSense budget management

The FastAPI budget router validates requests using the [shared backend contract](BACKEND_CONTRACT.md). Its request-scoped `BudgetService` uses Developer 1's session, authenticated user UUID, and mapped `Budget` and `Expense` classes. Budget writes touch the budget table. Spending totals come from the current expense records.

## API and service operations

Paths are relative to the application API prefix. All routes use Developer 1's JWT-backed current-user dependency through the integration provider.

| Method and path | Service method | Success |
| --- | --- | --- |
| `POST /budgets` | `create_budget(BudgetCreate)` | `201 BudgetResponse` |
| `GET /budgets` | `get_budgets(skip=0, limit=20)` | `200` array of `BudgetResponse` |
| `GET /budgets/{budget_id}` | `get_budget_by_id(budget_id)` | `200 BudgetResponse` |
| `PATCH /budgets/{budget_id}` | `update_budget(budget_id, BudgetUpdate)` | `200 BudgetResponse` |
| `DELETE /budgets/{budget_id}` | `delete_budget(budget_id)` | `204` with an empty body |
| `GET /budgets/{budget_id}/summary` | `get_budget_summary(budget_id)` | `200 BudgetSummary` |

Create accepts `category`, `budget_limit`, `month`, and `year`. Patch accepts any subset and preserves omitted fields. A supplied field requires a value. A zero limit is valid. The service sets `user_id` from authentication, and the request schemas reject server-managed fields. List, detail, summary, update, and delete all scope access to the authenticated user.

Example create body

```json
{
  "category": "Groceries",
  "month": 12,
  "year": 2026,
  "budget_limit": "10000.00"
}
```

Example summary body

```json
{
  "budget_id": "a5bb2d73-d472-4dc7-ae75-2d21967b0820",
  "category": "Groceries",
  "month": 12,
  "year": 2026,
  "budget_limit": "10000.00",
  "total_spent": "12000.25",
  "remaining_budget": "-2000.25"
}
```

The CRUD responses keep the `BudgetResponse` shape, including `id`, `user_id`, and `created_at`, and populate `total_spent` and `remaining_budget`. List accepts `skip` from `0` through the PostgreSQL signed 64-bit maximum and `limit` from `1` through `100`. Results sort by `year DESC, month DESC, id DESC`. The default page size is `20`.

## Budget changes during the month

**PROPOSED — REQUIRES TEAM APPROVAL.** A limit applies to the budget's stored calendar month. A limit-only PATCH updates the same row and recalculates `remaining_budget` against the entire month's existing spending, including expenses from before the change. The result is the same whether the request arrives mid-month, at month end, or in a later month. For example, PKR `6000.00` spent against an updated limit of `15000.00` leaves `9000.00`. A limit of `4000.00` leaves `-2000.00`, and a zero limit leaves `-6000.00`.

The current PATCH contract still permits an explicit `month` or `year` change and checks the destination period for duplicates. The composition layer can configure `BudgetService(..., allow_period_changes=False)` to lock those fields. A PATCH containing a locked field returns `422`. Limit and category edits retain their existing behavior. The PKR-only calculation remains provisional. The current budget row stores the effective limit, so historical limit versioning would need a separate approved contract.

Regression tests check owned limit-only writes, unchanged period and spending, Decimal values, and live summary re-reads after expense mutations. An isolated embedded SQL check exercised the generated PostgreSQL statements with synthetic rows. Production ORM, migration, and JWT integration remain pending.

## Spending totals

**PROPOSED — REQUIRES TEAM APPROVAL.** Budgets are denominated in PKR. The budget model has no currency field in the shared contract. The aggregate counts expenses whose `currency` is `PKR`. Other currencies are excluded from the total.

The query sums expenses with the same user and category and with `transaction_date` in `[first day of the month, first day of the next month)`. Transaction dates are already Asia/Karachi calendar dates under the shared contract. PostgreSQL derives the boundaries, including December to January, without converting dates to UTC timestamps.

A single query returns budgets and their totals using a correlated aggregate. A budget with no matching expenses has zero spending. `remaining_budget` equals `budget_limit - total_spent` and can be negative. PostgreSQL `numeric` performs the sum and subtraction. SQLAlchemy must return those values as Python `Decimal`, and Pydantic serializes them as JSON strings. The application applies no rounding. Stored precision and scale follow the shared database schema. Reads reflect subsequent expense updates and deletions because they query the current expense rows. [SQLAlchemy correlated queries](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#lateral-correlation)

## Errors, uniqueness, and transactions

| Status | Meaning |
| --- | --- |
| `401` | The shared current-user dependency rejected the request. |
| `404` | The budget is absent or belongs to another user. With the default error handler both return `{"detail":"Budget not found"}`. |
| `409` | A budget already exists for the authenticated user, category, month, and year. |
| `422` | The request body, UUID, or pagination parameters failed validation. |
| `503` | The router's integration provider is unconfigured. |

The service checks the monthly key before creating a budget. When a patch supplies a key field, it checks the effective key returned by the scoped update and rolls the update back if the key already exists. Two concurrent writes can pass the application check. Developer 1 must enforce `UNIQUE (user_id, category, month, year)` in PostgreSQL for a concurrency guarantee. The proposed name is `uq_budgets_user_category_month_year`. The service maps SQLSTATE `23505` for that constraint to `409` and lets unrelated database errors reach the shared error handler. Confirm the constraint name and driver diagnostics at integration.

The transaction policy follows the Expense module. A synchronous request session is injected into the service. Create, non-empty patch, and delete commit in the service and roll back on failure. Create flushes before querying the saved response. Reads and empty patches leave transaction cleanup to the session provider. Confirm this policy if the shared backend uses a unit of work or commits in `get_db()`.

## Wiring and verification

Use the same composition pattern as [Expense CRUD](EXPENSE_MODULE.md#transactions-and-integration). Bind the budget provider to Developer 1's actual `get_db` and authenticated-user dependencies, passing both existing mapped classes to the service. In the application's composition code, the wiring is equivalent to:

```python
def provide_budget_service(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BudgetService:
    return BudgetService(db, user.id, Budget, Expense)


app.dependency_overrides[get_budget_service] = provide_budget_service
app.include_router(budget_router)
```

Import `get_budget_service` and `router as budget_router` from `app.routes.budgets` and `BudgetService` from `app.services.budget_service`. Use the agreed application prefix when mounting. Confirm that `Expense.transaction_date` is a local calendar date, that money columns return `Decimal`, and that the budget model supplies an ID and an aware creation timestamp.

Run `python -m unittest discover -s backend/tests -v` from the repository root with the [existing test dependencies](EXPENSE_MODULE.md#verification). The budget tests exercise service transactions and PostgreSQL statement compilation through a mocked session, and mount the router with a test authentication provider. Live tests against Developer 1's mapped models, JWT dependency, and PostgreSQL schema are pending.
