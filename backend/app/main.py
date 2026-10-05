"""FastAPI entry point: `uvicorn app.main:app --reload`.

Each feature folder exposes a `router`; include it here as features are built, e.g.
    from app.auth.router import router as auth_router
    app.include_router(auth_router)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import settings

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


@app.get("/api/health")
def health() -> dict[str, str]:
    """Used by docker compose and Render to check the API is up."""
    return {"status": "ok"}
