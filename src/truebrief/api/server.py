"""
API Server - api/server.py

FastAPI application setup.
"""

import asyncio
import concurrent.futures
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging
from truebrief.api.rate_limit import limiter
from truebrief.api.routes import router
from truebrief.billing.billing_routes import router as billing_router
from truebrief.api.digest_routes import router as digest_router
from truebrief.api.push_routes import router as push_router
from truebrief.api.public_routes import router as public_router
from truebrief.apikeys.routes import router as apikeys_router
from postgrest.exceptions import APIError as PostgrestAPIError

# Setup logging.
# logging.basicConfig() writes everything to stderr, which makes Railway tag every
# routine INFO line as an error — so a log search for real errors returns a wall of
# successful DB calls and genuine incidents are invisible. Split the streams instead:
# INFO/DEBUG to stdout, WARNING and above to stderr.
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.INFO)
_stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
_stdout_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)
_stderr_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _stderr_handler], force=True)
logging.getLogger("truebrief").setLevel(logging.INFO)

# httpx logs every outbound request at INFO, including full query strings that carry
# user ids — noisy, and it leaks identifiers into the log stream.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# The interactive docs publish the full API surface — every route, parameter and schema.
# Useful in dev, an enumeration aid in production. Fail secure: docs are exposed only
# when ENV *explicitly* says development, so a missing or mistyped ENV closes them
# rather than opening them.
_docs_enabled = os.getenv("ENV", "").strip().lower() in ("development", "dev", "local", "test")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the Supabase TCP+TLS connection so the first user request is not
    # delayed by connection setup (otherwise 10-15s on fresh deployments).
    try:
        from truebrief.ledger.database import get_supabase
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(
                pool,
                lambda: get_supabase().table("topics").select("id").limit(1).execute(),
            )
        logger.info("Supabase connection warmed up")
    except Exception as e:
        logger.warning("Supabase warmup failed (non-fatal): %s", e)
    yield


app = FastAPI(
    title="TrueBrief API",
    description="API for the TrueBrief Intelligence Engine.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(PostgrestAPIError)
async def postgrest_error_handler(request: Request, exc: PostgrestAPIError):
    if exc.code == "22P02":  # invalid input syntax for type uuid
        return JSONResponse(status_code=422, content={"detail": "Invalid ID format — expected a UUID"})
    if exc.code == "PGRST205":  # table not found (missing migration)
        logger.error("DB table missing — run pending migrations in Supabase SQL Editor. Error: %s", exc.message)
        return JSONResponse(status_code=503, content={"detail": "Feature not available — database migration required"})
    logger.error("Unexpected database error: code=%s message=%s", exc.code, exc.message)
    return JSONResponse(status_code=500, content={"detail": "Database error"})

# CORS config — restrict to the deployed frontend URL in production
_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _frontend_url.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1/billing")
app.include_router(digest_router, prefix="/api/v1")
app.include_router(push_router, prefix="/api/v1")
app.include_router(apikeys_router, prefix="/api/v1")   # key management (Supabase-Auth-authed)
app.include_router(public_router, prefix="/v1")        # developer API (API-key-authed)

@app.get("/health")
def health_check():
    return {"status": "ok"}
