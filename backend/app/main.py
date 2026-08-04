from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message" : "Welcome to AI Sales Intelligence Platform"}

@app.get("/health")
def health():
    return {"status" : "healthy"}