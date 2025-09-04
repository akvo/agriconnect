from fastapi import FastAPI
from routers import auth

app = FastAPI(title="AgriConnect API", version="1.0.0")

# Include routers
app.include_router(auth.router)

@app.get("/")
def read_root():
    return {"Status": "OK"}
