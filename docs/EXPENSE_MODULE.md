# SpendSense expense management

The FastAPI router validates HTTP inputs against the [Phase 1 contract](BACKEND_CONTRACT.md) and calls a request-scoped `ExpenseService`. The service uses Developer 1's SQLAlchemy session and mapped `Expense` class. It returns `ExpenseResponse` objects validated from ORM attributes. Developer 1 supplies the authenticated user and mounts the router.

## Service operations

Each `ExpenseService(db, user_id, Expense)` is bound to the authenticated user's UUID and the request session.

| Method | Behavior |
| --- | --- |
| `create_expense(expense_data)` | Creates an expense with the authenticated user's `user_id` and the validated create fields. Returns the saved expense. |
| `get_expenses(skip=0, limit=20)` | Returns one page of the user's expenses in a single query. |
| `get_expense_by_id(expense_id)` | Returns the user's expense or `None`. |
| `update_expense(expense_id, expense_data)` | Updates only explicitly provided fields and returns the updated expense or `None`. An empty patch reads the current expense. |
| `delete_expense(expense_id)` | Deletes the user's expense and returns whether a row was removed. |

Create obtains `user_id` from the authenticated user. The list query filters by it. Reads, updates, and deletes by ID include both `user_id` and `id` in the SQL predicate. Update and delete use PostgreSQL `RETURNING` to report whether the scoped write matched a row. The delete statement targets the expense table. Developer 1 should verify its foreign-key and cascade behavior in the integrated schema. [SQLAlchemy ORM DML documentation](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html)

## HTTP API

Paths are relative to the application's API prefix. All operations use the shared JWT-backed current-user dependency when wired into the application.

| Method and path | Request | Success |
| --- | --- | --- |
| `POST /expenses` | `ExpenseCreate` JSON | `201` with `ExpenseResponse` |
| `GET /expenses` | Optional `skip` and `limit` query parameters | `200` with an array of `ExpenseResponse` objects |
| `GET /expenses/{expense_id}` | Expense UUID | `200` with `ExpenseResponse` |
| `PATCH /expenses/{expense_id}` | Expense UUID and `ExpenseUpdate` JSON | `200` with `ExpenseResponse` |
| `DELETE /expenses/{expense_id}` | Expense UUID | `204` with an empty body |

`POST /expenses` example body

```json
{
  "amount": "1250.50",
  "category": "Groceries",
  "description": "Weekly groceries",
  "transaction_date": "2026-11-10"
}
```

Example create response

```json
{
  "id": "a5bb2d73-d472-4dc7-ae75-2d21967b0820",
  "user_id": "3a4787ed-92c7-46de-8599-64fb14300c48",
  "created_at": "2026-11-10T08:00:00Z",
  "amount": "1250.50",
  "category": "Groceries",
  "description": "Weekly groceries",
  "transaction_date": "2026-11-10",
  "currency": "PKR",
  "payment_method": null
}
```

A patch body of `{"amount": "1300.00", "description": null}` changes the amount and clears the description. Omitted fields retain their values. The nullable fields are `description` and `payment_method`. Create and patch bodies reject server-managed fields such as `id`, `user_id`, and `created_at`.

Use decimal strings for amounts. The schemas accept exact JSON integers too, enforce positive expense amounts, and serialize money as JSON strings. The service passes `Decimal` through to the ORM. Confirm the database's `numeric` precision and scale before integration, since those constraints govern what PostgreSQL can store. `transaction_date` is a calendar date supplied in `YYYY-MM-DD`. The shared model supplies the timezone-aware `created_at` timestamp.

### Pagination

**PROPOSED — REQUIRES TEAM APPROVAL.** `skip` defaults to `0` and accepts non-negative offsets up to PostgreSQL's signed 64-bit limit. `limit` defaults to `20` and accepts `1–100`. Results sort by `transaction_date DESC, id DESC`. For example, `GET /expenses?skip=20&limit=20` requests the second page. An offset past the last row returns `[]`.

### Errors

| Status | Meaning |
| --- | --- |
| `401` | The shared JWT dependency rejected missing or invalid authentication. |
| `404` | The expense is absent or belongs to another user. Both cases return `{"detail":"Expense not found"}` with FastAPI's default error handler. |
| `422` | The request body, UUID, or pagination parameters failed validation. |
| `500` | An unexpected exception reached the application's error handler. Use the shared handler or FastAPI's default with debug disabled to keep database details out of the response. |
| `503` | The expense router was mounted before its integration provider was configured. The router stops before calling the service. |

Phase 2 validation cases are covered by `422`. The module has no additional domain operation that returns `400`. Final error formatting follows Developer 1's application-wide convention.

## Transactions and integration

**PROPOSED — REQUIRES TEAM APPROVAL.** The session is synchronous and request-scoped. The service commits each create, non-empty patch, or delete transaction and rolls back on a failed write, response validation, or commit. For create it flushes before reading the generated ID and timestamp. For create and update it validates the response before committing. Reads and empty patches leave the transaction lifecycle to the session dependency. Supply a session without unrelated pending writes, since a session commit applies to the whole transaction. Confirm ownership before registration if the foundation commits in its dependency or unit of work.

Confirm the mapped `Expense` fields, native UUIDs, nullable columns, `Decimal`-returning `numeric` column, generated UUID and timestamp, and delete constraints. The router also needs the actual session and authentication imports, a current-user UUID, the application prefix, and the shared error format.

In the application's composition code, import and register `router` and bind `get_expense_service` to a provider that uses the actual authentication and database dependencies. For example, if the shared dependencies and models have the following import paths:

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from .database import get_db
from .models import Expense, User
from .routes.auth import get_current_user
from .routes.expenses import get_expense_service, router as expense_router
from .services.expense_service import ExpenseService


def provide_expense_service(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExpenseService:
    return ExpenseService(db, user.id, Expense)


app.dependency_overrides[get_expense_service] = provide_expense_service
app.include_router(expense_router)
```

Use the real dependency import paths and mount under the agreed API prefix. The current-user dependency must reject invalid or absent credentials and return the authenticated user. The provider passes that user's UUID to the service. [FastAPI dependency override documentation](https://fastapi.tiangolo.com/advanced/testing-dependencies/)

## Verification

With Python 3.12, install the backend and test dependencies in a virtual environment and run from the repository root.

```sh
python -m pip install "fastapi>=0.115,<1" "pydantic>=2.9,<3" "SQLAlchemy>=2,<3" "httpx>=0.28,<1"
python -m unittest discover -s backend/tests -v
```

The service suite checks PostgreSQL statement compilation, ownership predicates, Decimal values, and transaction calls with a mocked session. The API suite mounts the router in FastAPI and supplies a test dependency override. Real JWT validation, PostgreSQL persistence, database-generated defaults, and cross-user isolation against the shared schema require integration tests with Developer 1's foundation and an isolated PostgreSQL database.
