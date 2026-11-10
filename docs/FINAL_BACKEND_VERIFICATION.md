# Final backend verification

The local branch is `feature/task-name`. Its available refs point to template commit `211385e`. The working tree contains uncommitted finance work. `feature/backend`, Developer 1's foundation, and frontend sources are absent from the available refs. The branch has no production application entry point, ORM models, JWT dependency, or deployed frontend to exercise. [Integration compatibility](INTEGRATION_COMPATIBILITY.md)

The repository's requirements file is a blank template. The checklist covers the official Phase 2 and Phase 3 requirements identifiable from the supplied Phase 7 and Phase 8 briefs and the existing finance contracts. Confirm the inventory against the team's official requirements document when it is available. “Tested” records local evidence and “Production verified” records actual integrated verification.

| Phase | Requirement | Implemented | Tested | Production verified | Blocker or evidence | Responsible developer |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | Expense create, read, list, update, and delete | Yes | Yes | No | Finance API fixtures and compiled owner-scoped SQL. Shared ORM and JWT needed. | Developer 2, Developer 1 integration |
| 2 | Budget create, read, list, update, delete, and summary | Yes | Yes | No | Finance API fixtures and scoped SQL. Shared ORM and JWT needed. | Developer 2, Developer 1 integration |
| 2 | Monthly budget uniqueness and duplicate conflict | Yes | Yes | No | Application check and named SQLSTATE conflict handling. Verify the database constraint and race on migrated PostgreSQL. | Developer 1 migration, Developer 2 handler |
| 2 | Mid-month limit changes retain prior spending and can leave negative balances | Yes | Yes | No | Limit-only PATCH tests and Phase 7 isolated SQL check. Policy and PKR-only scope await approval. | Developer 2, team approval |
| 2 | Natural-language expense parsing and editable confirmation | Yes | Yes | No | Synthetic drafts, mock Gemini HTTP, and separate confirmation call. Shared deployment and live model pending. | Developer 2, Developer 1 integration |
| 2 | Wallet and bank SMS parsing and non-expense classifications | Yes | Yes | No | Synthetic SMS fixtures, redaction, and provider mocks. Additive response fields and live model pending. | Developer 2, team approval |
| 2 | UUID, Decimal, currency, partial-update, and transaction rules | Yes | Yes | No | Schema, SQL, and rollback tests. Shared column scale, session policy, and migrations pending. | Developers 1 and 2 |
| 2 | Registration, login, JWT expiry, and production authorization | No | No | No | Actual foundation and isolated PostgreSQL absent. | Developer 1 |
| 3 | Monthly spending and transaction count with Decimal precision | Yes | Yes | No | Provisional service, API fixtures, and date-window tests. Shared Expense mapping pending. | Developer 2 provisional, Developer 1 approval |
| 3 | Category totals, counts, and spending concentration | Yes | Yes | No | Category percentages reconcile in local tests. Shared categories and endpoint approval pending. | Developer 2 provisional, Developer 1 approval |
| 3 | Spending trends, missing months, partial period, and December rollover | Yes | Yes | No | Local calculations and provisional API tests. Production PostgreSQL and JWT pending. | Developer 2 provisional, Developer 1 integration |
| 3 | Unusual-spending detection, minimum history, and deterministic explanation | Yes | Yes | No | Phase 7 rule, latest-expense check, and provisional endpoint tested. Policy and production history pending. | Developer 2 provisional, Developer 1 approval |
| 3 | Structured Gemini insights grounded in computed statistics | Yes | Yes | No | Mock HTTP confirms the shared adapter and constrained ranking. Live smoke test requires opt-in and credentials. | Developer 2 provisional, Developer 1 integration |
| 3 | Deterministic AI fallback and empty data | Yes | Yes | No | Local tests cover expected provider failures and invalid selections. Deployment pending. | Developer 2 provisional, Developer 1 integration |
| 3 | Analytics and insights API registration and user isolation | Yes | Yes | No | Exported router composes with existing finance routers in a test app. Production registration and JWT pending. | Developer 1 registration, Developer 2 provisional |
| 3 | Isolated PostgreSQL CRUD, analytics, rollback, and isolation acceptance | No | No | No | Foundation models, migrations, and test PostgreSQL unavailable. Mapper scaffolding retained. | Developers 1 and 2 |
| 3 | Frontend workflows and demonstration readiness | No | No | No | API contract and demo sequence prepared. Frontend source, authentication, and deployment pending. | Frontend owner and Developer 1 |

## Local verification and security

The final standard suite ran 123 tests with 119 passed, 0 failed, and 4 skipped. Three mapper tests require Developer 1's model exports and isolated configuration. The remaining skip is the opt-in live Gemini smoke test. Imports, compilation, and OpenAPI generation passed for 18 unique operations with all three routers mounted in a fixture app. Static expense parsing routes retain their own POST operations. Earlier embedded SQL evidence covers the budget calculation in isolation. Production PostgreSQL, JWT, Gemini, and browser integration remain unverified.

- The finance routes scope requests through injected authenticated UUIDs. Expense and budget queries bind owner predicates, and analytics rechecks owner and currency on repository results. Insights rejects mismatched budget owners. The test bearer verifies the dependency boundary. Developer 1 must still verify real JWT signature, expiry, identity extraction, and global error handling.
- The anomaly HTTP request bounds Decimal digits and fractional places. This prevents an extreme client exponent from driving unbounded arithmetic precision. The trusted saved-expense path still uses the shared stored Decimal values. Keep this guard aligned with the shared Numeric column contract.
- The shared adapter uses server-side credentials and bounded retries. Insights sends aggregate values and opaque IDs. The model cannot inject display text or change amounts. Existing SMS redaction masks recognized references, identifiers, authentication codes, numbers, and links before enrichment. Production body logging and provider data handling need verification in Developer 1's app.
- Parsing and anomaly checks do not persist expenses. Existing CRUD owns explicit confirmation and rollback. Duplicate monthly budget writes require the named PostgreSQL constraint for concurrent enforcement. Session type, ownership, rollback, and cleanup remain part of the production checks.

## Demo and merge gates

Run `bash scripts/test.sh` with the finance dependencies to demonstrate the contract tests. Use the frontend guide for the interactive sequence and the insights guide for the optional synthetic live provider check. [Frontend integration](FRONTEND_BACKEND_INTEGRATION.md) [Live smoke test](AI_FINANCIAL_INSIGHTS.md#verification)

The PR draft is ready for review. Opening the PR requires the `feature/backend` target and manually committed finance changes. Before a merge, Developer 1 must review overlapping analytics and insights work, approve the provisional routes and policies, bind shared dependencies, and run acceptance tests against disposable PostgreSQL and real JWTs. The frontend owner must wire the API and verify the demo flows, including deterministic fallback. Use synthetic inputs for the approved live Gemini check. [PR draft](FINANCE_MODULE_PR.md)
