from fastapi import FastAPI
from app.core.config import settings
from app.api.routes.users import router as user_router

app = FastAPI(
    title = settings.app_name,
    version = settings.app_version,   
)
app.include_router(user_router)
@app.get("/")
def root():
    return {"message" : "Welcome to AI Sales Intelligence Platform"}

@app.get("/health")
def health():
    return {"status" : "healthy"}