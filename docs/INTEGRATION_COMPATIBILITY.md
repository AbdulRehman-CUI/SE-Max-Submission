# SpendSense finance integration compatibility

The finance module was inspected on `feature/task-name`. Local `main`, `origin/main`, and the current branch all point to the template commit `211385e`. The working tree contains Developer 2's uncommitted finance files. `feature/backend`, a remote-tracking ref for it, and Developer 1's foundation files are absent from the available local refs. The comparison below therefore records the verified finance interface and the precise checks still required on the integration branch.

## Compatibility matrix

| Component and affected finance files | Verified Developer 2 interface | Developer 1 evidence and status | Failure if the interface differs and owner |
| --- | --- | --- | --- |
| Expense ORM · `expense_service.py`, `schemas.py` | `id`, `user_id`, `amount`, `category`, `description`, `transaction_date`, `currency`, `payment_method`, `created_at` | Model, relationships, defaults, and migrations unavailable. **Pending** | A missing or renamed column breaks statement construction. Incompatible types or missing defaults fail writes or response validation. Developer 1 supplies the mapped shape or proposes an explicit mapping for Developer 2 to review. |
| Budget ORM · `budget_service.py`, `schemas.py` | `id`, `user_id`, `category`, `budget_limit`, `month`, `year`, `created_at`. Totals are derived from Expense rows. | Model, foreign keys, and migrations unavailable. **Pending** | Missing columns break CRUD or totals. Without a database unique key, concurrent writes can create duplicates. Developer 1 owns the constraint and migrations. |
| User identity · both CRUD services | Providers supply a Python `UUID`. SQL predicates include the authenticated owner. Request models reject ownership fields. | `User` and the current-user return type unavailable. **Pending** | A string or integer passed directly to a service fails its UUID guard. Developer 1 confirms the model and the provider supplies the UUID from validated identity. |
| Database session · both CRUD services | Synchronous request-scoped SQLAlchemy `Session`. Services commit writes and roll back failures. The request dependency closes the session. | Session dependency, engine, driver, and transaction ownership unavailable. **Pending** | `AsyncSession` methods return awaitables and cannot drive these services. Competing commit ownership can commit unrelated work or fail during cleanup. Developers 1 and 2 agree on one transaction policy before wiring. |
| Authentication · `routes/expenses.py`, `routes/budgets.py` | `get_expense_service`, `get_budget_service`, and shared `get_expense_parser` provider seams. Default providers return `503`. | JWT signature and expiry validation, dependency import, error behavior, and identity object unavailable. **Pending** | Missing overrides leave routes unavailable. A provider that omits authentication could allow unauthorized access. Developer 1 wires the actual current-user dependency for every provider. |
| Router registration · both route modules | Exported routers expose 13 unique method/path pairs in a combined FastAPI app. | Application prefix, existing routes, and router registration unavailable. **Finance composition verified, production pending** | Duplicate registration can shadow routes or duplicate OpenAPI operations. Developer 1 mounts each router once under the agreed application prefix. |
| Expense response · `schemas.py`, `routes/expenses.py` | Bare Pydantic response objects and arrays. Money serializes as strings, IDs as UUID strings. | Shared response envelope and serialization conventions unavailable. **Pending** | Frontend consumers can receive an incompatible body, or ORM attribute validation can fail. Developer 1 confirms shared API conventions, then Developer 2 adapts finance response mapping if needed. |
| Budget response · `schemas.py`, `routes/budgets.py` | `BudgetResponse` and `BudgetSummary` expose Decimal spending and remaining amounts. | Shared response format and PKR-only policy approval unavailable. **Pending** | Mixing currencies yields misleading totals. Developer 1 and Developer 2 confirm currency policy and response shape before exposing aggregate endpoints. |
| Gemini · `ai_service.py`, `sms_service.py` | One async adapter and one parser service share model configuration, structured JSON, timeouts, and retries across both routes. | Shared Gemini client and analytics configuration unavailable. **Finance SDK transport verified with mocks, production pending** | Multiple clients can duplicate configuration and lifecycle work. Developer 1 provides one lifespan-owned async client or reuses the existing adapter and configuration. |
| Errors · both route modules | `404` for absent and non-owned records, `409` for duplicates, `422` for invalid input, and safe `502`/`503`/`504` parsing failures. | Global handlers, HTTP envelope, and logging policies unavailable. **Pending** | A custom formatter can expose input or provider details, or change response shape. Developer 1 verifies handler behavior and disables sensitive request and error logging. |

The combined-router test verifies request and response schemas, status codes, bearer security metadata, and rejection of unauthenticated requests across the 13 operations using test dependencies. Authenticated `POST /expenses/parse` and `POST /expenses/parse-sms` reached their static handlers without invoking Expense CRUD. Only a separate `POST /expenses` passed the reviewed `ExpenseCreate` payload to CRUD. The test mounts under `/api` as a fixture. The production prefix is still pending. Malformed item IDs continue to use the existing UUID validation behavior.

## Developer 1 integration changes

Confirm the actual imports before applying the example. The code below assumes the proposed module paths and belongs in Developer 1's application composition. A shared parser can be created once in the application's lifespan with `ExpenseAIService(GeminiExpenseProvider(shared_async_client, configured_model))`. Keep the default unavailable provider if Gemini is unconfigured. The parser requires authentication and no session.

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import Budget, Expense, User
from .routes.auth import get_current_user
from .routes.budgets import get_budget_service, router as budget_router
from .routes.expenses import get_expense_parser, get_expense_service, router as expense_router
from .services.ai_service import ExpenseAIService
from .services.budget_service import BudgetService
from .services.expense_service import ExpenseService

CurrentUser = Annotated[User, Depends(get_current_user)]
RequestSession = Annotated[Session, Depends(get_db)]


def provide_expenses(user: CurrentUser, db: RequestSession) -> ExpenseService:
    return ExpenseService(db, user.id, Expense)


def provide_budgets(user: CurrentUser, db: RequestSession) -> BudgetService:
    return BudgetService(db, user.id, Budget, Expense)


def provide_parser(request: Request, user: CurrentUser) -> ExpenseAIService:
    parser = getattr(request.app.state, "expense_parser", None)
    if parser is None:
        raise HTTPException(503, "Expense parsing is temporarily unavailable.")
    return parser


def register_finance(app: FastAPI, api_prefix: str) -> None:
    app.dependency_overrides[get_expense_service] = provide_expenses
    app.dependency_overrides[get_budget_service] = provide_budgets
    app.dependency_overrides[get_expense_parser] = provide_parser
    for router in (expense_router, budget_router):
        app.include_router(router, prefix=api_prefix, dependencies=[Depends(get_current_user)])
```

Call the composition function once when creating the app. The parser provider reads the service when a request arrives, after the application's lifespan starts. A router-level dependency lets the declared bearer scheme appear in OpenAPI when `get_current_user` uses FastAPI's bearer or OAuth2 dependency. Dependency overrides enforce runtime dependencies but do not by themselves document them. Use the shared authentication handler and validate its JWT signature, expiry, and user lookup on the integrated app.

For a synchronous foundation, `get_db()` should yield the shared request session and close it on every exit. Finance services flush as needed, commit successful writes, and roll back failed writes. Verify that the dependency does not separately own those commits and that authentication does not leave unrelated pending writes in the same session. If the foundation supplies only `AsyncSession`, agree on an async finance refactor before registration. Do not pass the async session to the current constructors or introduce another engine.

### ORM and migration checks

- Confirm native UUID values for primary and foreign keys and FKs from each `user_id` to the shared user. Confirm generated `id` and aware `created_at` values are available by flush. Inspect deletion cascades and relationship loading against the shared schema.
- Match `Expense.transaction_date` to PostgreSQL `DATE` and treat it as the Asia/Karachi calendar date. Confirm `description` and `payment_method` are nullable, and that category and currency return strings compatible with the schema. Approve category normalization and the meaning of a PKR-only budget before using totals.
- Map `amount` and `budget_limit` to `NUMERIC` with `asdecimal=True`. Agree on precision and scale and test the boundary values. Finance validation does not round to a database scale in advance.
- Confirm the monthly unique key is present in the deployed PostgreSQL schema. If missing, Developer 1 should identify and resolve existing duplicates, then add the named constraint in the existing migration framework. In an Alembic project, the proposed operation is `op.create_unique_constraint("uq_budgets_user_category_month_year", actual_budget_table_name, ["user_id", "category", "month", "year"])`. The conflict handler expects SQLSTATE `23505` and this constraint name from the shared driver's diagnostics. Confirm both with a concurrent create test.
- Confirm the shared migration history, database driver, logging, and response envelope on `feature/backend`. No Developer 1 schema or migration was changed during this phase.

## Verification and security findings

The finance regression suite uses SQLAlchemy statement compilation and mocked sessions, a combined in-process FastAPI app, and mocked Gemini HTTP responses. The audit reviewed owner predicates on all finance reads and writes, UUID and Decimal validation, ignored or rejected model fields, retry limits, provider error sanitization, and the absence of persistence calls in either parsing flow. A synthetic all-letter verification code was previously forwarded in redacted SMS text. The finance-owned redactor now masks labeled letter-only and mixed authentication codes, and a regression test checks that the original codes never reach the provider. Masking is partial and raw SMS or API keys must stay out of application logs.

The local suite deliberately skips three mapper checks until the actual models can be imported. With the foundation and isolated test configuration available, set `SPENDSENSE_TEST_MODELS_MODULE` to the importable module exporting the real `User`, `Expense`, and `Budget`. Run `python -m unittest backend.tests.test_finance_integration.SharedORMCompatibilityTests -v` with the foundation on the Python import path. The checks inspect mapped attributes and compile PostgreSQL SQL without opening a session or database connection. Adapt the model import to the actual export path after inspection.

Production PostgreSQL, JWT, and Gemini were unavailable for verification. Local SQL compilation and mocked SDK calls do not establish those integrations. Once the foundation is present, use its actual test setup and a disposable PostgreSQL database to run this sequence:

1. Apply the shared migrations and register and sign in two test users. Verify rejection of missing, invalid, and expired tokens and the app's error envelope.
2. Run expense and budget CRUD as one user and attempt cross-user list, read, update, delete, and budget summary operations as the other. Verify missing and non-owned IDs return the same `404`.
3. Check a December budget across the January boundary with mixed currencies, a second category, and another owner's expenses. Verify exact Decimal totals, negative remainders, and recalculation after expense changes. Race two identical budget writes and verify a single row and a `409`. Induce a write failure and verify rollback and request-session cleanup.
4. Call both parsing routes with and without valid JWTs, with Gemini mocked, and verify expense row counts change only after an authenticated confirmation request to `POST /expenses`. Check the app's OpenAPI and all route registrations for duplicates. Separately run a team-authorized live Gemini smoke test using synthetic text.

## Merge comparison status

Phase 8 adds an unmounted provisional analytics router. It composes with the expense and budget routers in the fixture app for 18 distinct operations. Bind its analytics provider to the same authenticated user and session used by finance, then reuse the shared Gemini adapter for insights. Compare these routes with Developer 1's actual analytics and insights implementation before mounting. [Registration example](AI_FINANCIAL_INSIGHTS.md#integration) [Final verification](FINAL_BACKEND_VERIFICATION.md)

The local common baseline is `211385e`. The only tracked finance delta against that baseline is `.env.example`; finance implementation and documents are still untracked. The template's existing CI workflow expects `scripts/test.sh`, which was added to install finance test dependencies and run the suite. Compare this script and the environment example with the integration branch's actual dependency and CI setup before the PR is opened.

When an authorized local ref is available, use `git merge-base HEAD feature/backend`, `git diff --name-status <base> feature/backend`, and `git show feature/backend:<path>` to compare the candidate paths with the complete local worktree inventory from `git status --short --untracked-files=all`. Inspect overlaps in `.env.example`, the CI test command, `backend/app/schemas.py`, finance routes and services, model and authentication imports, the shared Gemini client, and contract docs. Neither the overlap nor conflicts with `feature/backend` can be determined from `origin/main`.
