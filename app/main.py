from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import create_tables
from app.routes import router as receipts_router
from app.analytics_routes import router as analytics_router
from app.product_routes import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    create_tables()
    yield

app = FastAPI(
    title="Albert Heijn Receipts API",
    description="API wrapper for Albert Heijn receipts",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(receipts_router)
app.include_router(analytics_router)
app.include_router(products_router)

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/dashboard")
@app.get("/")
async def dashboard():
    """Serve the home page dashboard."""
    return FileResponse(static_dir / "index.html")
