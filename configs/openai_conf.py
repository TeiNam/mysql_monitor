import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class OpenAISettings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 2000
    OPENAI_TEMPERATURE: float = 0.3

    class Config:
        env_file = ".env"
        extra = "ignore"

openai_settings = OpenAISettings()

# OpenAI API 키 검증
if not openai_settings.OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables or .env file.")