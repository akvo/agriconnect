from fastapi import FastAPI

from routers import (
    admin_users,
    administrative,
    auth,
    callbacks,
    customers,
    knowledge_base,
    service_tokens,
    whatsapp,
)

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
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(administrative.router, prefix="/api")
app.include_router(callbacks.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(knowledge_base.router, prefix="/api")
app.include_router(service_tokens.router, prefix="/api")
app.include_router(whatsapp.router, prefix="/api")


@app.get("/api/health-check", tags=["health-check"])
def read_root():
    return {"Status": "OK"}
