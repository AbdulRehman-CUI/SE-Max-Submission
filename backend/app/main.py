from __future__ import annotations

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.database import check_db_connection
from app.routes import auth, expenses, budgets, analytics

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered personal finance management API.",
    version="0.1.0",
    debug=settings.DEBUG,
)

app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(budgets.router)
app.include_router(analytics.router)


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
