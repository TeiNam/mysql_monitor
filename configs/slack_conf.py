import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache

# .env 파일 로드
load_dotenv()


class SlackSettings(BaseSettings):
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL")
    HOST: str = os.getenv("HOST", "localhost")

    # 추가 설정들
    aes_key: str = os.getenv("AES_KEY")
    aes_iv: str = os.getenv("AES_IV")
    mongodb_uri: str = os.getenv("MONGODB_URI")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME")
    aws_regions: str = os.getenv("AWS_REGIONS")
    account: str = os.getenv("ACCOUNT")
    aws_account_ids: str = os.getenv("AWS_ACCOUNT_IDS")
    openai_api_key: str = os.getenv("OPENAI_API_KEY")

    class Config:
        env_file = ".env"
        extra = "ignore"  # 추가 필드 무시


@lru_cache()
def get_slack_settings():
    return SlackSettings()


slack_settings = get_slack_settings()
SLACK_WEBHOOK_URL = slack_settings.SLACK_WEBHOOK_URL
HOST = slack_settings.HOST

# 설정 값 검증
if not SLACK_WEBHOOK_URL:
    raise ValueError("SLACK_WEBHOOK_URL is not set in the environment variables.")
if not HOST:
    raise ValueError("HOST is not set in the environment variables.")