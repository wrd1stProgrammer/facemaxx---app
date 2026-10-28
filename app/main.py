import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.services.transient_image_cleanup import cleanup_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        lifespan=lifespan,
        title="Facemaxx API",
        version="0.1.0",
        description="FastAPI backend for Facemaxx AI face analysis and glow-up reports.",
    )

    if settings.parsed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.parsed_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(api_router)
    return app


app = create_app()

