from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import traceback

from modules.mongodb_connector import MongoDBConnector
from modules.time_utils import get_kst_time
from configs.log_conf import setup_logging
from configs.app_conf import app_settings

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
    debug=app_settings.DEBUG
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await MongoDBConnector.initialize()
    logger.info(f"{get_kst_time()} - MongoDB connection initialized.")
    yield
    if MongoDBConnector.client:
        await MongoDBConnector.close()
        logger.info(f"{get_kst_time()} - MongoDB connection closed.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=app_settings.STATIC_FILES_DIR), name="static")
templates = Jinja2Templates(directory=app_settings.TEMPLATES_DIR)

@app.get("/favicon.ico")
async def get_favicon():
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

# Mounting the APIs
for route, module_name in app_settings.API_MAPPING.items():
    try:
        module = __import__(module_name, fromlist=['app'])
        if hasattr(module, 'app'):
            app.mount(route, module.app)
        else:
            logger.error(f"Module {module_name} does not have 'app' attribute")
            # 여기에 fallback 로직 추가
            from fastapi import APIRouter
            router = APIRouter()
            for name, obj in module.__dict__.items():
                if isinstance(obj, APIRouter):
                    app.include_router(obj, prefix=route)
                    break
    except ImportError as e:
        logger.error(f"Failed to import module {module_name}: {e}")
    except Exception as e:
        logger.error(f"Error mounting API at {route}: {e}")

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

__all__ = ['app']

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=app_settings.HOST, port=app_settings.PORT, reload=True)