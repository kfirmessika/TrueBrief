"""
API Server - api/server.py

FastAPI application setup.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from truebrief.api.routes import router
from truebrief.billing.billing_routes import router as billing_router
from truebrief.api.digest_routes import router as digest_router

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

@app.get("/health")
def health_check():
    return {"status": "ok"}
