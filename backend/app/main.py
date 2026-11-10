from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import check_db_connection, get_db
from app.models import Budget, Expense, User
from app.routes import analytics, auth, budgets, expenses, provisional_analytics
from app.services.ai_service import ExpenseAIService, GeminiExpenseProvider
from app.services.budget_service import BudgetService
from app.services.expense_service import ExpenseService
from app.services.financial_insights_service import FinancialInsightsService
from app.services.spending_analytics_service import SQLAlchemySpendingRepository, SpendingAnalyticsService


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        yield
        return
    async with GeminiExpenseProvider.connect(
        api_key, settings.GEMINI_MODEL, timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
    ) as provider:
        app.state.gemini_provider = provider
        try:
            yield
        finally:
            del app.state.gemini_provider

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered personal finance management API.",
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

CurrentUser = Annotated[User, Depends(auth.get_current_user)]
RequestSession = Annotated[Session, Depends(get_db)]


def provide_expenses(user: CurrentUser, db: RequestSession) -> ExpenseService:
    return ExpenseService(db, user.id, Expense)


def provide_budgets(user: CurrentUser, db: RequestSession) -> BudgetService:
    return BudgetService(db, user.id, Budget, Expense)


def provide_parser(request: Request, user: CurrentUser) -> ExpenseAIService:
    provider = getattr(request.app.state, "gemini_provider", None)
    if provider is None:
        raise HTTPException(503, "Expense parsing is temporarily unavailable.")
    return ExpenseAIService(provider)


def provide_analytics(user: CurrentUser, db: RequestSession) -> SpendingAnalyticsService:
    return SpendingAnalyticsService(SQLAlchemySpendingRepository(db, Expense), user.id)


def provide_insights(request: Request) -> FinancialInsightsService:
    return FinancialInsightsService(getattr(request.app.state, "gemini_provider", None))


app.dependency_overrides.update({
    expenses.get_expense_service: provide_expenses,
    budgets.get_budget_service: provide_budgets,
    expenses.get_expense_parser: provide_parser,
    provisional_analytics.get_spending_analytics: provide_analytics,
    provisional_analytics.get_financial_insights: provide_insights,
})

app.include_router(auth.router)
protected = [Depends(auth.get_current_user)]
app.include_router(expenses.router, dependencies=protected)
app.include_router(budgets.router, dependencies=protected)
app.include_router(analytics.router)
app.include_router(provisional_analytics.router, prefix="/v2", dependencies=protected)


class DBHealthResponse(BaseModel):
    status: str
    message: str


@app.get(
    "/health/db",
    tags=["Health"],
    response_model=DBHealthResponse,
    summary="Check database connectivity",
    responses={
        status.HTTP_200_OK: {
            "description": "Database is reachable and responding to queries",
            "content": {
                "application/json": {
                    "example": {"status": "healthy", "message": "Database connection successful"}
                }
            },
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is unreachable",
            "content": {
                "application/json": {
                    "example": {"status": "unhealthy", "message": "Database connectivity check failed: OperationalError"}
                }
            },
        },
    },
)
def health_db():
    is_connected, message = check_db_connection()
    if not is_connected:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "message": message},
        )
    return {"status": "healthy", "message": message}


@app.get("/", tags=["Health"])
def root() -> dict:
    return {
        "app": settings.APP_NAME,
        "status": "running",
    }
