"""FastAPI entry point: `uvicorn app.main:app --reload`.

Each feature folder exposes a `router`; include it in create_app() under the /api/v1 prefix as features
are built, e.g.
    from app.allocations.router import router as allocations_router
    app.include_router(allocations_router, prefix=API_V1_PREFIX)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.allocations.router import router as allocations_router
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.limits import LimitRequestSize
from app.customers.router import router as customers_router
from app.dashboard.router import router as dashboard_router
from app.invoices.public_router import router as public_invoices_router
from app.invoices.router import router as invoices_router
from app.paystack.router import router as paystack_router
from app.reconciliation.router import router as reconciliation_router
from app.statements.router import router as statements_router
from app.transactions.router import router as transactions_router
from app.workspaces.router import router as workspaces_router

# Every feature route lives under /api/v1 (DECISIONS D-36). The version is added here, in one place:
# each router only knows its own path (e.g. "/invoices"). A breaking change later would get a v2
# router mounted next to this one, so old clients and the Paystack webhook URL keep working.
API_V1_PREFIX = "/api/v1"


def health() -> dict[str, str]:
    """Used by docker compose and Render to check the API is up.

    Deliberately not versioned: it is a probe for the hosting platform, not part of the API contract (D-36).
    """
    return {"status": "ok"}


def create_app() -> FastAPI:
    """Build the app. A function (not just module code) so tests can build one per environment."""
    # The interactive docs (/docs, /openapi.json) list every route and field: handy locally, a free map
    # for an attacker in production, so they are off there (D-45). Frontend types are generated locally.
    development = settings.environment == "development"
    app = FastAPI(
        title="Reconcile API",
        version="0.1.0",
        docs_url="/docs" if development else None,
        redoc_url="/redoc" if development else None,
        openapi_url="/openapi.json" if development else None,
    )

    # The browser blocks calls from localhost:3000 to localhost:8000 unless the API allows that origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Refuse oversized bodies before anything reads them (D-44).
    app.add_middleware(LimitRequestSize)

    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(customers_router, prefix=API_V1_PREFIX)
    app.include_router(invoices_router, prefix=API_V1_PREFIX)
    app.include_router(public_invoices_router, prefix=API_V1_PREFIX)
    app.include_router(statements_router, prefix=API_V1_PREFIX)
    app.include_router(transactions_router, prefix=API_V1_PREFIX)
    app.include_router(reconciliation_router, prefix=API_V1_PREFIX)
    app.include_router(allocations_router, prefix=API_V1_PREFIX)
    app.include_router(paystack_router, prefix=API_V1_PREFIX)
    app.include_router(dashboard_router, prefix=API_V1_PREFIX)
    app.include_router(audit_router, prefix=API_V1_PREFIX)
    app.include_router(workspaces_router, prefix=API_V1_PREFIX)

    app.add_api_route("/api/health", health, methods=["GET"])
    return app


app = create_app()
