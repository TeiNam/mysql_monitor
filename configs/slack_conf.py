import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache

# .env 파일 로드
load_dotenv()

class SlackSettings(BaseSettings):
    SLACK_API_TOKEN: str = os.getenv("SLACK_API_TOKEN")
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL")
    HOST: str = os.getenv("HOST")

    class Config:
        env_file = ".env"

@lru_cache()
def get_slack_settings():
    return SlackSettings()

slack_settings = get_slack_settings()
SLACK_API_TOKEN = slack_settings.SLACK_API_TOKEN
SLACK_WEBHOOK_URL = slack_settings.SLACK_WEBHOOK_URL
HOST = slack_settings.HOST

# 설정 값 검증
if not SLACK_API_TOKEN:
    raise ValueError("SLACK_API_TOKEN is not set in the environment variables.")
if not SLACK_WEBHOOK_URL:
    raise ValueError("SLACK_WEBHOOK_URL is not set in the environment variables.")
if not HOST:
    raise ValueError("HOST is not set in the environment variables.")