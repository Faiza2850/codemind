from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from dotenv import load_dotenv

import os
# Ensure data dirs exist on startup
os.makedirs("data/uploads", exist_ok=True)
os.makedirs("data/indexes", exist_ok=True)

load_dotenv()

app = FastAPI(
    title="Codebase Intelligence Engine",
    description="AI that reads and explains entire codebases",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "Codebase Intelligence Engine 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy", "version": "0.2.0"}