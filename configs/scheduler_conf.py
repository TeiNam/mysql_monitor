from pydantic_settings import BaseSettings

class SchedulerSettings(BaseSettings):
    COLLECT_DAILY_METRICS_HOUR: int = 1  # KST 기준 새벽 1시
    COLLECT_DAILY_METRICS_MINUTE: int = 0

    class Config:
        env_file = ".env"
        extra = "ignore"