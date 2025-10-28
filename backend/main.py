import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from routers import (
    admin_users,
    administrative,
    auth,
    callbacks,
    customers,
    devices,
    knowledge_base,
    messages,
    service_tokens,
    whatsapp,
    tickets,
    ws,
    storage,
    crop_types,
)
from fastapi.staticfiles import StaticFiles
from services.akvo_rag_service import get_akvo_rag_service
# from tasks.retry_scheduler import start_retry_scheduler, stop_retry_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Replaces deprecated on_event decorator.
    """
    # Startup: Validate Akvo RAG configuration
    logger.info("✓ Application startup - validating Akvo RAG configuration")
    rag_service = get_akvo_rag_service()
    if not rag_service.is_configured():
        logger.warning(
            "⚠ Akvo RAG not fully configured. "
            "Set AKVO_RAG_APP_ACCESS_TOKEN and "
            "AKVO_RAG_APP_KNOWLEDGE_BASE_ID environment variables."
        )
    else:
        logger.info(
            f"✓ Akvo RAG configured with KB ID: "
            f"{rag_service.knowledge_base_id}"
        )

    # Startup: start retry scheduler for failed messages
    # logger.info("✓ Starting retry scheduler for failed messages")
    # start_retry_scheduler()

    yield

    # Shutdown: stop retry scheduler
    # logger.info("✓ Stopping retry scheduler")
    # stop_retry_scheduler()

    # Shutdown: cleanup if needed
    logger.info("✓ Application shutdown")


app = FastAPI(
    title="AgriConnect API",
    version="1.0.0",
    description="API for AgriConnect Application",
    ignore_trailing_slash=True,
    contact={
        "name": "AgriConnect Support",
    },
    license_info={
        "name": "GNU General Public License v3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.en.html",
    },
    redoc_url="/api/redoc",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(administrative.router, prefix="/api")
app.include_router(callbacks.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(knowledge_base.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(service_tokens.router, prefix="/api")
app.include_router(whatsapp.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(storage.router)
app.include_router(crop_types.router, prefix="/api")

# Ensure storage directory exists before mounting
os.makedirs("storage", exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


# Health check endpoint
@app.get("/api/health-check", tags=["health-check"])
def read_root():
    return {"Status": "OK"}


# Mount Socket.IO at /ws/socket.io path
# Socket.IO will handle /ws/socket.io/* requests
# Must be mounted AFTER all FastAPI routes are defined
app.mount("/ws/socket.io", ws.sio_app)
