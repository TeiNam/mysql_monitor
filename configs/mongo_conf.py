import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache

load_dotenv()

class MongoSettings(BaseSettings):
    # MongoDB 연결 설정
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "mgmt_db")
    # 컬렉션 이름 설정
    MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION: str = os.getenv("MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION",
                                                              "mysql_slow_query_instance")
    MONGO_SLOW_LOG_COLLECTION: str = os.getenv("MONGO_SLOW_LOG_COLLECTION", "mysql_slow_queries")
    MONGO_SLOW_LOG_PLAN_COLLECTION: str = os.getenv("MONGO_SLOW_LOG_PLAN_COLLECTION", "mysql_slow_query_plans")
    MONGO_COM_STATUS_COLLECTION: str = os.getenv("MONGO_COM_STATUS_COLLECTION", "mysql_com_status")
    MONGO_RDS_INSTANCE_ALL_STAT_COLLECTION: str= os.getenv("MONGO_RDS_INSTANCE_ALL_STAT_COLLECTION","aws_rds_instance_all_stat")


    class Config:
        env_file = ".env"
        extra = "ignore"  # 추가 필드 허용

@lru_cache()
def get_mongo_settings():
    return MongoSettings()

mongo_settings = get_mongo_settings()
MONGODB_URI = mongo_settings.MONGODB_URI
MONGODB_DB_NAME = mongo_settings.MONGODB_DB_NAME

# 설정 값 검증
if not MONGODB_URI:
    raise ValueError("MONGODB_URI is not set in the environment variables.")
if not MONGODB_DB_NAME:
    raise ValueError("MONGODB_DB_NAME is not set in the environment variables.")