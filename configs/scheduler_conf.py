from pydantic_settings import BaseSettings

class SchedulerSettings(BaseSettings):
    COLLECT_DAILY_METRICS_HOUR: int = 1
    COLLECT_DAILY_METRICS_MINUTE: int = 0
    CLEANUP_OLD_FILES_HOUR: int = 2
    CLEANUP_OLD_FILES_MINUTE: int = 0

    class Config:
        env_file = ".env"
        extra = "ignore"