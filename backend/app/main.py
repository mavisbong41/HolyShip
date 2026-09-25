import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.router import _build_sync_service, router
from backend.app.core.config import Settings, get_settings
from backend.app.data_lifecycle.runtime import DataLifecycleRuntime
from backend.app.ingestion.runtime import IngestionRuntime
from backend.app.ingestion.graph_sync import GraphSyncRuntime
from backend.app.storage.database import SessionLocal

logger = logging.getLogger(__name__)


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
        data_lifecycle_runtime = DataLifecycleRuntime(
            configured,
            session_factory=SessionLocal,
        )
        graph_sync_runtime = GraphSyncRuntime(configured, SessionLocal, processor_factory)
        app.state.ingestion_runtime = runtime
        app.state.data_lifecycle_runtime = data_lifecycle_runtime
        app.state.graph_sync_runtime = graph_sync_runtime
        runtime.start()
        data_lifecycle_runtime.start()
        graph_sync_runtime.start()
        try:
            yield
        finally:
            data_lifecycle_runtime.stop()
            graph_sync_runtime.stop()
            runtime.stop()

    application = FastAPI(
        title=configured.app_name,
        description="HolyShip Shipping Document Verification — product-facing API over persisted processing results",
        version="0.7.0",
        lifespan=lifespan,
    )
    if configured.cors_origin_list or configured.cors_origin_regex:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=configured.cors_origin_list,
            allow_origin_regex=configured.cors_origin_regex,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server error processing %s %s: %s", request.method, request.url.path, exc)
        headers: dict[str, str] = {}
        origin = request.headers.get("origin")
        if origin:
            allowed_origins = configured.cors_origin_list
            if "*" in allowed_origins:
                headers["Access-Control-Allow-Origin"] = "*"
            elif origin in allowed_origins:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Vary"] = "Origin"
            elif configured.cors_allow_origin_regex:
                import re
                if re.match(configured.cors_allow_origin_regex, origin):
                    headers["Access-Control-Allow-Origin"] = origin
                    headers["Vary"] = "Origin"
            if "Access-Control-Allow-Origin" in headers:
                headers["Access-Control-Allow-Methods"] = "*"
                headers["Access-Control-Allow-Headers"] = "*"
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error", "error": str(exc)},
            headers=headers,
        )

    application.include_router(router, prefix="/api")
    return application


app = create_app()
