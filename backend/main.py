from fastapi import FastAPI
from routers import auth, admin_users, whatsapp, customers

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
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(whatsapp.router, prefix="/api")
app.include_router(customers.router, prefix="/api")


@app.get("/")
def read_root():
    return {"Status": "OK"}
