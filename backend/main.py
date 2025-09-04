from fastapi import FastAPI
from routers import auth

app = FastAPI(
        title="AgriConnect API",
        version="1.0.0",
        # documentation_url="/api/docs",  # Custom docs URL
        description="API for AgriConnect Application",
        contact={
            "name": "AgriConnect Support",
            "url": "https://www.agriconnect.com/support"
            },
        license_info={
            "name": "GNU General Public License v3",
            "url": "https://www.gnu.org/licenses/gpl-3.0.en.html",
            },
        redoc_url="/api/redoc",
        docs_url="/api/docs"
)

# Include routers
app.include_router(auth.router, prefix="/api")

@app.get("/")
def read_root():
    return {"Status": "OK"}
