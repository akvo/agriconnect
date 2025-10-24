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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Replaces deprecated on_event decorator.
    """
    # Startup: register with akvo-rag
    logger.info("✓ Application startup - registering with akvo-rag")
    rag_service = get_akvo_rag_service()
    await rag_service.register_app()

    yield

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
