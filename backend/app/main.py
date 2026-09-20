from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import _build_sync_service, router
from backend.app.core.config import Settings, get_settings
from backend.app.ingestion.runtime import IngestionRuntime
from backend.app.storage.database import SessionLocal


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        def processor_factory(session):
            service = _build_sync_service(session, configured)
            return service.sync_one

        runtime = IngestionRuntime(
            configured,
            session_factory=SessionLocal,
            processor_factory=processor_factory,
        )
        app.state.ingestion_runtime = runtime
        runtime.start()
        try:
            yield
        finally:
            runtime.stop()

    application = FastAPI(
        title=configured.app_name,
        description="HolyShip Shipping Document Verification — product-facing API over persisted processing results",
        version="0.7.0",
        lifespan=lifespan,
    )
    if configured.cors_origin_list:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=configured.cors_origin_list,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    application.include_router(router, prefix="/api")
    return application


app = create_app()
