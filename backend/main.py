from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from contextlib import asynccontextmanager
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# 初始化日志（确保爬虫日志handler已注册）
from services import log_store  # noqa

from database import create_db_and_tables, init_admin_user, engine
from api import auth, search, admin, ai, chat, points
from services.crawler import crawl_all, start_scheduler
import threading

def _run_crawl_in_thread():
    threading.Thread(target=crawl_all, kwargs={"session": None}, daemon=True).start()
    start_scheduler()
from limiter import limiter

scheduler = AsyncIOScheduler()

# 前端静态文件目录
FRONTEND_DIR = Path(__file__).resolve().parent / "assets" / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"
AVATARS_DIR = Path(__file__).resolve().parent / "assets" / "avatars"

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    init_admin_user()

    from config import get_settings
    settings = get_settings()
    scheduler.add_job(
        _run_crawl_in_thread,
        IntervalTrigger(minutes=settings.CRAWL_INTERVAL_MINUTES),
        id="crawler_job",
        replace_existing=True,
    )
    scheduler.start()

    yield
    scheduler.shutdown()

from config import get_settings
settings = get_settings()

app = FastAPI(title="石化助手", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# SPA fallback 函数式中间件（装饰器方式，支持 call_next 风格）
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
    if index_path.exists():
        return FileResponse(index_path)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(ai.router, prefix="/api/admin/ai", tags=["ai"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(points.router, prefix="/api/points", tags=["points"])

# Avatar static files
if AVATARS_DIR.exists():
    app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR), html=False), name="avatars")

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

# 静态文件（仅 assets）
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR), html=False), name="assets")
