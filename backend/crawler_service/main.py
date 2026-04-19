# backend/crawler_service/main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading

from database import create_db_and_tables
from services.crawler import crawl_all, start_scheduler
from crawler_service.routers.crawl_admin import router as crawl_admin_router

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

@app.get("/health")
def health():
    return {"status": "ok", "service": "crawler"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
