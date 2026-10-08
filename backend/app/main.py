"""FastAPI application factory, middleware, exception handlers and health check."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.files import router as files_router
from app.core.config import settings
from app.core.exceptions import GeospatialAPIError
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db

logger = get_logger(__name__)

API_VERSION = "1.0.0"
_MARSHALLOWING_SLACK_BYTES = 64 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("%s v%s started (%s)", settings.app_name, API_VERSION, settings.environment)
    yield


def create_app() -> FastAPI:
    setup_logging(settings.log_level)
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    init_db()

    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        description=(
            "Upload KML or Shapefile ZIP files, store them in PostgreSQL and "
            "retrieve per-feature area/length measurements."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def enforce_upload_size_limit(
        request: Request,
        call_next: Callable[[Request], Awaitable[JSONResponse]],
    ) -> JSONResponse:
        """Reject oversized uploads with 413 before the body is read."""
        header = request.headers.get("content-length")
        if request.method == "POST" and header and header.isdigit():
            limit = settings.max_upload_size_bytes + _MARSHALLOWING_SLACK_BYTES
            if int(header) > limit:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Upload exceeds the {settings.max_upload_size_mb} MB size limit."
                        )
                    },
                )
        return await call_next(request)

    @app.exception_handler(GeospatialAPIError)
    async def handle_geospatial_error(_: Request, exc: GeospatialAPIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = [f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()]
        detail = "; ".join(messages) or "Invalid request."
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/health", tags=["health"], summary="Liveness probe")
    def health() -> dict:
        return {"status": "healthy"}

    @app.get("/", tags=["health"], summary="API root", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": API_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    app.include_router(files_router)
    return app


app = create_app()
