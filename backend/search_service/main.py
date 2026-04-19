# backend/search_service/main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from database import create_db_and_tables, init_admin_user
from limiter import limiter
from routers.auth import router as auth_router
from routers.chat import router as chat_router
from routers.admin import router as admin_router
from routers.points import router as points_router
from routers.search import router as search_router
from routers.ai import router as ai_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    init_admin_user()
    yield

app = FastAPI(title="石化助手", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FRONTEND_DIR = Path(__file__).resolve().parent / "assets" / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"
AVATARS_DIR = Path(__file__).resolve().parent.parent / "assets" / "avatars"

@app.middleware("http")
async def spa_fallback_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        return await call_next(request)
    if path.startswith("/assets/"):
        relative_path = path[len("/assets/"):].lstrip("/")
        file_path = ASSETS_DIR / relative_path
        if file_path.is_file():
            return FileResponse(file_path)
        return await call_next(request)
    index_path = FRONTEND_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(points_router, prefix="/api/points", tags=["points"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(ai_router, prefix="/api/admin/ai", tags=["ai"])

if AVATARS_DIR.exists():
    app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR), html=False), name="avatars")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "search"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR), html=False), name="assets")