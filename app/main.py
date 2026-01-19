from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router as receipts_router

app = FastAPI(
    title="Albert Heijn Receipts API",
    description="API wrapper for Albert Heijn receipts",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(receipts_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
