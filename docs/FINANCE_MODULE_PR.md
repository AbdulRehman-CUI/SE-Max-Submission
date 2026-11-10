# Finance module pull request draft

**Suggested title** `feat: implement SpendSense finance module with expense, budget and AI parsing`

**Source** `feature/task-name`

**Intended base** `feature/backend`

SpendSense users can manage expenses and monthly budgets and turn manually entered text or pasted bank and wallet SMS into expense drafts. Draft extraction leaves persistence to a separate authenticated expense creation request after review.

## Changes for review

| Phase | Behavior |
| --- | --- |
| Shared contracts | Validates UUID identifiers, Decimal money, local calendar dates, request fields, and partial updates. |
| Expense management | `POST` and `GET /expenses`; `GET`, `PATCH`, and `DELETE /expenses/{expense_id}`. Lists are paginated. Reads and writes are scoped to the authenticated owner. |
| Budget management | `POST` and `GET /budgets`; `GET`, `PATCH`, and `DELETE /budgets/{budget_id}`; `GET /budgets/{budget_id}/summary`. Totals use current expenses for the owner, category, and calendar month. Duplicate monthly budgets return `409` when detected. |
| Natural-language drafts | `POST /expenses/parse` extracts a validated draft from English, Roman Urdu, or mixed-language text using structured Gemini responses. Relative dates use Asia/Karachi. |
| SMS drafts | `POST /expenses/parse-sms` classifies pasted notifications and distinguishes completed expense candidates from credits, failures, reversals, withdrawals, transfers, and balance notices. It validates amounts and dates locally, and uses the same Gemini adapter for enrichment of eligible drafts. |
| Analytics and insights | Provisional monthly, category, trend, anomaly, and insight routes use owner-scoped computed statistics. Gemini ranks fact IDs and the server renders claims with deterministic fallback. |

The Phase 6 audit also fixed a redaction gap that allowed letter-only verification codes to reach the Gemini adapter. SMS redaction now masks labeled authentication codes along with references, identifiers, numbers, and URLs. Both parsing routes validate structured responses and use safe provider errors. Neither parser calls Expense CRUD or opens a database session.

## Files in the proposed PR

- Add `backend/app/schemas.py`, `backend/app/routes/{expenses,budgets}.py`, and `backend/app/services/{expense_service,budget_service,ai_service,sms_service}.py`.
- Add `backend/tests/{test_schemas,test_expenses,test_budgets,test_ai_expenses,test_sms_parsing,test_finance_integration}.py`.
- Add `backend/app/spending_analytics_schemas.py`, `backend/app/routes/provisional_analytics.py`, `backend/app/services/{spending_analytics_service,financial_insights_service}.py`, and their analytics and insights tests.
- Add `docs/{BACKEND_CONTRACT,EXPENSE_MODULE,BUDGET_MODULE,AI_EXPENSE_PARSING,SMS_PARSING,INTEGRATION_COMPATIBILITY,FINANCE_MODULE_PR}.md` and `scripts/test.sh`.
- Add `docs/{ANALYTICS_AND_ANOMALIES,AI_FINANCIAL_INSIGHTS,FRONTEND_BACKEND_INTEGRATION,FINAL_BACKEND_VERIFICATION}.md`.
- Update `.env.example` with `GEMINI_API_KEY` and `GEMINI_MODEL` placeholders.

## Verification

The Phase 8 suite completed locally with **119 passed, 0 failed, 4 skipped**. The skips cover three Developer 1 mapper checks and the live Gemini smoke test. The combined router tests mount 18 operations with test authentication and verify OpenAPI and request and response schemas. Confirmation tests check that only the separate create request calls Expense CRUD. CRUD tests use mocked sessions and PostgreSQL statement compilation. Gemini tests use mocked HTTP with the official SDK. Production JWT, a live PostgreSQL database, a live Gemini request, and frontend integration are pending. [Final verification](FINAL_BACKEND_VERIFICATION.md)

The repository's existing CI workflow invokes `scripts/test.sh`. Run it with Python 3.12 and Bash. The script installs the finance test dependencies before running `unittest`. The Phase 8 local run used `unittest` with installed dependencies. Reconcile this entry point with the shared dependency and CI setup on the target branch.

## Integration requirements and limitations

`GEMINI_API_KEY` is required when bootstrapping the Gemini client from the environment. `GEMINI_MODEL` is optional and defaults to `gemini-3.8-flash`. The application can supply an already configured client. PostgreSQL and JWT configuration belong to the foundation and must use its actual variable names. The optional `SPENDSENSE_TEST_MODELS_MODULE` selects the shared mapper module for offline contract checks.

Developer 1 needs to wire the exported routers to the shared current-user dependency, synchronous request session, mapped models, and lifespan-owned Gemini client. Confirm the session commit policy, response and error conventions, ORM numeric types and precision, the named monthly budget uniqueness constraint, and approval for PKR-only budget totals and the additive SMS response fields. SMS sources were exercised with synthetic examples. Redaction is partial and repeated SMS pastes have no persistent duplicate check. See the [compatibility matrix and wiring example](INTEGRATION_COMPATIBILITY.md).

## Merge checklist

- [ ] Make Developer 1's foundation available on `feature/backend` and inspect the actual contracts before changing production composition.
- [ ] Compare the branches and resolve overlaps in schemas, dependencies, environment variables, CI, and contract documentation with both developers.
- [ ] Record the AI-assisted implementation and verification in the team's AI usage log for PR review.
- [ ] Confirm the finance model mappings, session policy, authentication dependencies, Gemini client ownership, and router prefix. Apply the approved unique-key migration where needed.
- [ ] Review and stage only the intended finance changes, then create the PR manually against `feature/backend`.
- [ ] Run the mapper checks and isolated PostgreSQL and JWT acceptance tests, plus an approved Gemini smoke test using synthetic input. Require CI and teammate review before merging.

The PR description is prepared for review. Opening it requires the target branch and committed finance changes. Integration merge readiness depends on the shared foundation and the pending checks above.
