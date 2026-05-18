"""
API Server - api/server.py

FastAPI application setup.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging
from truebrief.api.rate_limit import limiter
from truebrief.api.routes import router
from truebrief.billing.billing_routes import router as billing_router
from truebrief.api.digest_routes import router as digest_router
from truebrief.api.push_routes import router as push_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("truebrief").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TrueBrief API",
    description="API for the TrueBrief Intelligence Engine.",
    version="1.0.0",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1/billing")
app.include_router(digest_router, prefix="/api/v1")
app.include_router(push_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
