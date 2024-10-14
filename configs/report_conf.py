import os
from pydantic_settings import BaseSettings
from datetime import datetime

class ReportSettings(BaseSettings):
    BASE_REPORT_DIR: str = os.getenv("BASE_REPORT_DIR", "reports")
    INSTANCE_STATS_API_URL: str = os.getenv("INSTANCE_STATS_API_URL", "http://localhost:8000/api/v1/reports/daily-instance-statistics")

    class Config:
        env_file = ".env"
        extra = "ignore"

    def get_report_dir(self, date: datetime = None) -> str:
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        return os.path.join(self.BASE_REPORT_DIR, date_str)

report_settings = ReportSettings()