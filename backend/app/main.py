"""FastAPI entry point: `uvicorn app.main:app --reload`.

Each feature folder exposes a `router`; include it here as features are built, e.g.
    from app.allocations.router import router as allocations_router
from app.auth.router import router as auth_router
    app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(invoices_router)
app.include_router(public_invoices_router)
app.include_router(statements_router)
app.include_router(transactions_router)
app.include_router(reconciliation_router)
app.include_router(allocations_router)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.allocations.router import router as allocations_router
from app.auth.router import router as auth_router
from app.core.config import settings
from app.customers.router import router as customers_router
from app.invoices.public_router import router as public_invoices_router
from app.invoices.router import router as invoices_router
from app.reconciliation.router import router as reconciliation_router
from app.statements.router import router as statements_router
from app.transactions.router import router as transactions_router

app = FastAPI(title="Reconcile API", version="0.1.0")

# The browser blocks calls from localhost:3000 to localhost:8000 unless the API allows that origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(invoices_router)
app.include_router(public_invoices_router)
app.include_router(statements_router)
app.include_router(transactions_router)
app.include_router(reconciliation_router)
app.include_router(allocations_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Used by docker compose and Render to check the API is up."""
    return {"status": "ok"}
