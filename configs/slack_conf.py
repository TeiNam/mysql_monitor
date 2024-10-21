import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

# .env 파일 로드
load_dotenv()


class SlackSettings(BaseSettings):
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    HOST: str = os.getenv("HOST", "localhost")

    # aws_account_ids를 선택적 필드로 변경
    aws_account_ids: Optional[str] = None

    # 다른 필드들도 필요에 따라 Optional로 설정하거나 기본값 제공
    aes_key: Optional[str] = None
    aes_iv: Optional[str] = None
    mongodb_uri: Optional[str] = None
    mongodb_db_name: Optional[str] = None
    aws_regions: Optional[str] = None
    account: Optional[str] = None
    openai_api_key: Optional[str] = None

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
if HOST == "localhost":
    print(
        "Warning: HOST is set to default value 'localhost'. Consider setting it explicitly in the environment variables.")