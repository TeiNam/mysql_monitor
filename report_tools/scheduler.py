import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any
import pytz
from fastapi import HTTPException

from configs.scheduler_conf import SchedulerSettings
from report_tools.prometheus_daily_metrics import collect_daily_metrics

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 스케줄러 설정 로드
scheduler_settings = SchedulerSettings()

# KST 시간대 설정
kst = pytz.timezone('Asia/Seoul')


class ReportScheduler:
    def __init__(self):
        self.tasks: Dict[str, Callable] = {
            "collect_daily_metrics": collect_daily_metrics
        }

    async def run_task(self, task_name: str):
        task = self.tasks.get(task_name)
        if task:
            try:
                await task()
                logger.info(f"Task {task_name} completed successfully")
            except HTTPException as he:
                logger.error(f"HTTP error in task {task_name}: {he}")
            except Exception as e:
                logger.error(f"Error in task {task_name}: {str(e)}")
        else:
            logger.error(f"Task {task_name} not found")

    async def schedule_task(self, task_name: str, hour: int, minute: int):
        while True:
            now = datetime.now(kst)
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)

            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Next run of {task_name} scheduled at {next_run}")

            await asyncio.sleep(wait_seconds)
            await self.run_task(task_name)

    def add_task(self, task_name: str, task: Callable):
        self.tasks[task_name] = task
        logger.info(f"Task {task_name} added to scheduler")

    def remove_task(self, task_name: str):
        if task_name in self.tasks:
            del self.tasks[task_name]
            logger.info(f"Task {task_name} removed from scheduler")
        else:
            logger.warning(f"Task {task_name} not found in scheduler")

    async def start(self):
        tasks = [
            self.schedule_task("collect_daily_metrics",
                               scheduler_settings.COLLECT_DAILY_METRICS_HOUR,
                               scheduler_settings.COLLECT_DAILY_METRICS_MINUTE)
        ]
        await asyncio.gather(*tasks)


scheduler = ReportScheduler()


def start_scheduler():
    asyncio.run(scheduler.start())


if __name__ == "__main__":
    start_scheduler()