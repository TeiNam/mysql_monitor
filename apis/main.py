import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import traceback

from modules.mongodb_connector import MongoDBConnector
from modules.time_utils import get_kst_time
from configs.log_conf import setup_logging
from configs.app_conf import app_settings

from .routes.instance_setup import router as instance_setup_router


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await MongoDBConnector.initialize()
    logger.info(f"{get_kst_time()} - MongoDB connection initialized.")
    yield
    if MongoDBConnector.client:
        await MongoDBConnector.close()
        logger.info(f"{get_kst_time()} - MongoDB connection closed.")

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

app.include_router(instance_setup_router, prefix="/api/v1/instance_setup")  # Updated router inclusion


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
        content={"message": "Internal server error", "error": error_msg},
    )