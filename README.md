# SpendSense

> AI-powered personal finance management for tracking expenses, managing budgets, and understanding spending.

## What it does

SpendSense is a full-stack personal finance application. Users can create an account, record and edit expenses, set monthly category budgets, review spending analytics, and optionally use Gemini-powered text or SMS parsing to create expense drafts and generate financial insights.

## Problem and user

SpendSense is designed for individuals who want a simple way to track day-to-day spending and compare it with monthly budgets. It combines manual expense entry with optional AI-assisted parsing while keeping the user in control: parsed expenses must be reviewed before they are saved.

## Live deployment

- **URL / install link:** Not configured in this repository.
- **Platform:** Local web application; production deployment requires hosting the FastAPI backend, a PostgreSQL-compatible database, and the built frontend.

## Judge quick start (under 5 minutes)

The project currently provides a local quick start. No hosted demo account or live deployment is configured.

1. Install Python 3.10+ and Node.js 24.
2. From the repository root, create the backend environment and install dependencies:
   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```
3. Set a random `SECRET_KEY` in `backend\.env`. The default SQLite sandbox database needs no PostgreSQL installation.
4. Initialize the database and start the backend:
   ```powershell
   .venv\Scripts\python -c "from app import models; from app.database import Base, engine; Base.metadata.create_all(engine)"
   .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
5. In a second terminal, install and start the frontend:
   ```powershell
   cd frontend
   npm ci
   Copy-Item .env.example .env.local
   npm run dev
   ```
6. Open http://127.0.0.1:5173, register a new account, and explore the dashboard, expenses, budgets, analytics, and insights pages.

## Test accounts

No shared test accounts are configured. Create a disposable account through the registration page or use synthetic accounts created by the automated tests.

| Role | Username / email | Password |
|------|------------------|----------|
| Local user | Create locally | Use a disposable password |

## Run locally

### Prerequisites

- Windows PowerShell, macOS, or Linux
- Python 3.10 or newer
- Node.js 24 and npm
- No database server is required for local development; SQLite is used by default
- Optional: a Google Gemini API key for AI expense parsing, SMS parsing, and provider-backed insights
- Optional: PostgreSQL for deployment or the opt-in PostgreSQL integration test

### Setup

#### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend\.env` and set at least:

```env
SECRET_KEY=replace_with_a_long_random_secret
```

The default database is:

```env
DATABASE_URL=sqlite:///./.sandbox/spendsense.db
```

The SQLite file is created under `backend\.sandbox\` when the backend connects. It is separate from `.venv` and is ignored by Git.

#### Frontend

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
```

The default frontend API configuration is:

```env
VITE_API_BASE_URL=/api
```

Vite proxies `/api/*` to FastAPI at `http://127.0.0.1:8000` and removes the `/api` prefix.

### Environment variables

Backend variables are documented in [`backend/.env.example`](backend/.env.example):

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | No | SQLite sandbox by default; can be replaced with a PostgreSQL URL |
| `SECRET_KEY` | Yes | Signs and validates JWT access tokens |
| `ALGORITHM` | No | JWT algorithm; defaults to `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT lifetime; defaults to 30 minutes |
| `APP_NAME` | No | Backend application name |
| `DEBUG` | No | Enables FastAPI/SQLAlchemy debug logging |
| `GEMINI_API_KEY` | No | Enables Gemini-backed parsing and provider-backed insights |
| `GEMINI_MODEL` | No | Gemini model name |
| `GEMINI_TIMEOUT_SECONDS` | No | Gemini request timeout |

Frontend variables are documented in [`frontend/.env.example`](frontend/.env.example):

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | No | API base URL; defaults to `/api` |

Never commit `.env`, `.env.local`, passwords, API keys, JWT secrets, or real personal financial data.

### Run

Initialize the local schema once from `backend`:

```powershell
.venv\Scripts\python -c "from app import models; from app.database import Base, engine; Base.metadata.create_all(engine)"
```

Start the backend in terminal 1:

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in terminal 2:

```powershell
cd frontend
npm run dev
```

Open the frontend at http://127.0.0.1:5173. FastAPI API documentation is available at http://127.0.0.1:8000/docs and database health is available at http://127.0.0.1:8000/health/db.

The main frontend routes are:

- `/` — landing page
- `/login` and `/register` — authentication
- `/dashboard` — overview
- `/expenses` — expense CRUD
- `/budgets` — monthly category budgets
- `/ai-assistant` — AI expense text parsing
- `/sms-parser` — SMS expense parsing
- `/analytics` — spending analytics and anomalies
- `/insights` — financial insights
- `/settings` — account settings

### Run tests

Frontend checks, from `frontend`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

Frontend end-to-end tests:

```powershell
npx playwright install chromium
npm run test:e2e
```

Backend tests, from the repository root:

```powershell
backend\.venv\Scripts\python -m unittest discover -s backend/tests -v
```

The backend suite uses mocked/unit coverage for most services and skips opt-in live Gemini and PostgreSQL tests unless their environment variables are explicitly provided. The PostgreSQL integration test requires `SPENDSENSE_TEST_POSTGRES_URL` pointing to an empty disposable loopback database.

## Known limitations

- No live deployment URL or shared demo account is configured.
- The default SQLite sandbox is intended for local development, not multi-user production hosting.
- Production should use PostgreSQL, HTTPS, and a production-grade secret-management strategy.
- Gemini features require a server-side `GEMINI_API_KEY`; without it, AI expense parsing is unavailable and insights use the deterministic fallback where supported.
- The backend currently uses bearer tokens stored by the frontend in tab-scoped `sessionStorage`; it does not provide refresh tokens or an HttpOnly cookie flow.
- A production deployment using a separate frontend and backend origin must configure CORS or use a reverse proxy.
- Database schema initialization currently uses SQLAlchemy `create_all`; production schema evolution should use the existing migration tooling.
- No migration, backup, monitoring, or hosted deployment configuration is included in this repository.

## Documentation

- [Frontend and backend setup](frontend/README.md)
- [Requirements](docs/requirements.md)
- [Design](docs/design.md)
- [Testing](docs/testing.md)
- [Frontend/backend integration](docs/FRONTEND_BACKEND_INTEGRATION.md)
- [Backend contract](docs/BACKEND_CONTRACT.md)
- [Expense module](docs/EXPENSE_MODULE.md)
- [Budget module](docs/BUDGET_MODULE.md)
- [Analytics and anomalies](docs/ANALYTICS_AND_ANOMALIES.md)
- [AI expense parsing](docs/AI_EXPENSE_PARSING.md)
- [AI financial insights](docs/AI_FINANCIAL_INSIGHTS.md)
- [SMS parsing](docs/SMS_PARSING.md)
- [Merge integration notes](docs/MERGE_INTEGRATION.md)
- [AI usage log](docs/ai-usage-log.md)
- [Submission checklist](SUBMISSION.md)

## Team

Team member names and role assignments have not been recorded in this repository.

| Name | Role |
|------|------|
| Not specified | Not specified |
