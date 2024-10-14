import os
import logging
import traceback

from modules.mongodb_connector import MongoDBConnector
from modules.time_utils import get_kst_time
from configs.app_conf import app_settings
from configs.report_conf import report_settings
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .routes.instance_setup import router as instance_setup_router
from .routes.slow_query import router as slow_queries_router
from .routes.slow_query_explain import router as slow_query_explain_router
from .routes.mysql_com_status import router as mysql_com_status_router
from .routes.mysql_disk_usage import router as mysql_disk_usage_router
from .routes.slow_query_stat import router as slow_query_stat_router

from report_tools import instance_statistics
from report_tools import report_generator
from report_tools.scheduler import start_scheduler
import threading

# Setup logging
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await MongoDBConnector.initialize()
    logger.info(f"MongoDB connection initialized at {get_kst_time()}")
    yield
    if MongoDBConnector.client:
        await MongoDBConnector.close()
        logger.info(f"MongoDB connection closed at {get_kst_time()}")

app = FastAPI(
    title=app_settings.APP_TITLE,
    description=app_settings.APP_DESCRIPTION,
    version=app_settings.APP_VERSION,
    debug=app_settings.DEBUG,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=app_settings.STATIC_FILES_DIR), name="static")
templates = Jinja2Templates(directory=app_settings.TEMPLATES_DIR)

# FastAPI 앱 설정 후
threading.Thread(target=start_scheduler, daemon=True).start()

app.include_router(instance_setup_router, prefix="/api/v1/instance_setup", tags=["Instance Setup"])
app.include_router(slow_queries_router, prefix="/api/v1/query_tool", tags=["Slow Queries"])
app.include_router(slow_query_explain_router, prefix="/api/v1/query_tool", tags=["Query Explain"])
app.include_router(mysql_com_status_router, prefix="/api/v1", tags=["MySQL Command Status"])
app.include_router(mysql_disk_usage_router, prefix="/api/v1", tags=["MySQL Disk Usage"])
app.include_router(slow_query_stat_router, prefix="/api/v1", tags=["Slow Query Stats"])
app.include_router(instance_statistics.router, prefix="/api/v1/reports", tags=["Instance Statistics"])
app.include_router(report_generator.router, prefix="/api/v1/reports", tags=["Report Generator"])


# 기본 리포트 디렉토리 생성
os.makedirs(report_settings.BASE_REPORT_DIR, exist_ok=True)

@app.get("/favicon.ico")
async def get_favicon():
    if os.path.exists(app_settings.FAVICON_PATH):
        return FileResponse(app_settings.FAVICON_PATH)
    else:
        return Response(content="", media_type="image/x-icon")

@app.get("/", tags=["Health Check"])
async def health_check():
    try:
        db = await MongoDBConnector.get_database()
        await db.command('ping')
        return JSONResponse(content={"status": "healthy", "database": "connected"}, status_code=200)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(content={"status": "unhealthy", "database": "disconnected"}, status_code=500)

@app.get("/sql-plan", tags=["UI"])
async def sql_explain(request: Request):
    return templates.TemplateResponse("sql_explain.html", {"request": request})

@app.get("/instance-setup", tags=["UI"])
async def instance_setup(request: Request):
    return templates.TemplateResponse("instance_setup.html", {"request": request})

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    error_msg = f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}"
    logger.error(error_msg)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "error": str(exc)},
    )