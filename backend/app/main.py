from fastapi import FastAPI

from backend.app.api.router import router
from backend.app.core.config import get_settings

app = FastAPI(
    title=get_settings().app_name,
    description="HolyShip Shipping Document Verification — product-facing API over persisted processing results",
    version="0.7.0",
)

app.include_router(router, prefix="/api")
