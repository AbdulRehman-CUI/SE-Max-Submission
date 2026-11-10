# SpendSense frontend

SpendSense is a React and TypeScript workspace for tracking expenses, managing category budgets, and understanding spending. The public landing page uses an explicitly labeled illustrative preview. Every record in the signed-in workspace comes from the FastAPI backend.

## Local development

Use Node.js 24 and npm. Local development uses a SQLite sandbox database, so PostgreSQL is not required. In a PowerShell terminal at the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `SECRET_KEY` in the backend `.env`. The default `DATABASE_URL` creates `backend/.sandbox/spendsense.db`. For an empty development database, initialize the schema once, then start FastAPI:

```powershell
.venv\Scripts\python -c "from app import models; from app.database import Base, engine; Base.metadata.create_all(engine)"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For a database created before the backend merge, follow the migration notes in [Merge integration](../docs/MERGE_INTEGRATION.md). The AI expense and SMS parsers require server-side `GEMINI_API_KEY` and a model available to that key. Without Gemini, parsing shows the backend's unavailable response and insights still display the deterministic report.

In a second PowerShell terminal at the repository root:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open [the local frontend](http://127.0.0.1:5173). The default `VITE_API_URL=/api` routes browser requests through Vite's development proxy to FastAPI at `http://127.0.0.1:8000`. Vite removes the proxy prefix, so requests arrive at FastAPI paths such as `/auth/me` and `/expenses`.

## API and account behavior

| UI | Mounted FastAPI operations |
| --- | --- |
| Registration, sign-in, profile | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Expenses | `GET /expenses`, `POST /expenses`, `PATCH /expenses/{id}`, `DELETE /expenses/{id}` |
| Budgets | `GET /budgets`, `POST /budgets`, `PATCH /budgets/{id}`, `DELETE /budgets/{id}`, `GET /budgets/{id}/summary` |
| AI and SMS review | `POST /expenses/parse`, `POST /expenses/parse-sms`, then `POST /expenses` after confirmation |
| Dashboard and analytics | `GET /analytics/summary`, `GET /v2/analytics/monthly`, `GET /v2/analytics/trends`, `POST /v2/analytics/anomalies/check` |
| Insights | `GET /v2/analytics/insights` |

The frontend uses the merged backend's month-scoped response shapes, including categories in the monthly response and generation source in insights. Expense and budget writes send exact decimal strings. PKR is the reporting currency for totals and budgets. Other expense currencies remain visible in the expense list. Backend reporting uses Asia/Karachi. The workspace surfaces unavailable APIs as errors and offers retry for read operations.

The bearer token is stored in tab-scoped `sessionStorage` so refreshing the tab can restore the account with `/auth/me`. Logout and an expired session clear the token. Same-origin scripts can read browser storage, so the token is still exposed if the frontend has a script injection vulnerability. The backend currently provides a bearer token and no refresh endpoint or HttpOnly cookie flow. Serve the production app over HTTPS. SMS input and parsed drafts are transient React state, and saved requests include the reviewed expense fields only.

## CORS and deployment

For production, build the frontend and host `dist/` with an SPA rewrite to `index.html` for browser routes. The default same-origin setup requires a reverse proxy that forwards `/api/*` to FastAPI and strips `/api`. For the separate Vercel deployment, set `VITE_API_URL` to the backend URL before building. Vite preview uses the same local proxy for development verification. See [Vercel deployment](../docs/VERCEL_DEPLOYMENT.md).

When the browser calls a separate FastAPI origin directly, configure that server or its gateway to allow the exact frontend origin, the required methods (`GET`, `POST`, `PATCH`, `DELETE`, and preflight `OPTIONS`), and the `Authorization` and `Content-Type` headers. The backend allows the configured `ALLOWED_ORIGINS` and the required API methods and headers. Keep database credentials, JWT secrets, and Gemini credentials in the backend environment.

## Verification

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npm run preview
```

`npm test` covers API authentication, decimal payloads, pagination, safe errors, parser confirmation, and ineligible SMS handling using controlled responses.

```powershell
npx playwright install chromium
npm run test:e2e
```

The browser suite covers the public landing page, reduced motion, responsive widths, and protected routes. To also exercise sign-up, expense and budget CRUD, analytics, insights fallback, session restoration, and logout, start FastAPI on port 8000 with a **disposable database** and no Gemini key, then run:

```powershell
$env:SPENDSENSE_E2E_LIVE = "1"
npm run test:e2e
```

The live test creates a synthetic account. Set `SPENDSENSE_BROWSER=msedge` to use installed Microsoft Edge in place of downloaded Chromium.
