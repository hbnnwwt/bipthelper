# backend/crawler_service/main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from contextlib import asynccontextmanager
import threading

from database import create_db_and_tables
from services.crawler import crawl_all, start_scheduler
from crawler_service.routers.crawl_admin import router as crawl_admin_router
from crawler_service.routers.crawler_auth import router as auth_router
from crawler_service.routers.crawler_admin import router as crawler_admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    start_scheduler()
    yield

app = FastAPI(title="Crawler Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl_admin_router, prefix="/admin", tags=["crawler"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(crawler_admin_router, prefix="/api/admin", tags=["admin"])

FRONTEND_DIR = Path(__file__).resolve().parent / "assets" / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"

@app.get("/health")
def health():
    return {"status": "ok", "service": "crawler"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.middleware("http")
async def spa_fallback_middleware(request: Request, call_next):
    path = request.url.path
    # API routes handled by routers
    if path.startswith("/api/") or path.startswith("/admin/"):
        return await call_next(request)
    # Static assets
    if path.startswith("/assets/"):
        relative_path = path[len("/assets/"):].lstrip("/")
        file_path = ASSETS_DIR / relative_path
        if file_path.is_file():
            return FileResponse(file_path)
        return await call_next(request)
    # SPA fallback for all other paths
    index_path = FRONTEND_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return await call_next(request)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR), html=False), name="assets")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
