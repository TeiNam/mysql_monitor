import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class AppSettings(BaseSettings):
    # 앱 메타데이터
    APP_TITLE: str = "Monitoring Tool API"
    APP_DESCRIPTION: str = "API for monitoring MySQL and managing related data"
    APP_VERSION: str = "1.0.0"

    # 앱 설정
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))

    # 프로젝트 구조 설정
    ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FRONTEND_DIR: str = os.path.join(ROOT_DIR, "frontend")
    STATIC_FILES_DIR: str = os.path.join(FRONTEND_DIR, "static")
    TEMPLATES_DIR: str = os.path.join(FRONTEND_DIR, "templates")
    FAVICON_PATH: str = os.path.join(FRONTEND_DIR, "img", "favicon.ico")

    # CORS 설정
    ALLOWED_ORIGINS: list = ["http://localhost:8000"]

    # 기타 설정
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # 데이터베이스 설정
    DATABASE_URL: str = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "mysql_monitor")

    class Config:
        env_file = ".env"
        extra = "ignore"  # 추가 필드 허용

@lru_cache()
def get_app_settings():
    return AppSettings()

app_settings = get_app_settings()

# 설정 값 검증
if not app_settings.HOST:
    raise ValueError("HOST is not set in the environment variables.")
if not app_settings.PORT:
    raise ValueError("PORT is not set in the environment variables.")