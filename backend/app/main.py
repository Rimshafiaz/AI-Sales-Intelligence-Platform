from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title = settings.app_name,
    version = settings.app_version,   
)

@app.get("/")
def root():
    return {"message" : "Welcome to AI Sales Intelligence Platform"}

@app.get("/health")
def health():
    return {"status" : "healthy"}