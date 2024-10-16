import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any
import pytz
from fastapi import HTTPException
import httpx
import os
import shutil

from configs.scheduler_conf import SchedulerSettings
from configs.app_conf import app_settings
from configs.report_conf import report_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler_settings = SchedulerSettings()
kst = pytz.timezone('Asia/Seoul')

class ReportScheduler:
    def __init__(self):
        self.tasks: Dict[str, Callable] = {
            "collect_daily_metrics": self.collect_daily_metrics,
            "cleanup_old_files": self.cleanup_old_files
        }

    async def collect_daily_metrics(self):
        url = f"{app_settings.BASE_URL}/api/v1/prometheus/collect-daily-metrics"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                logger.info("Daily metrics collected successfully")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred while collecting daily metrics: {e}")
            except Exception as e:
                logger.error(f"An error occurred while collecting daily metrics: {e}")

    async def cleanup_old_files(self):
        try:
            base_dir = report_settings.BASE_REPORT_DIR
            cutoff_date = datetime.now() - timedelta(days=31)
            deleted_files = 0
            deleted_folders = 0

            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                item_time = datetime.fromtimestamp(os.path.getctime(item_path))

                if item_time < cutoff_date:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        deleted_files += 1
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        deleted_folders += 1

            logger.info(f"Cleanup completed: {deleted_files} files and {deleted_folders} folders deleted")
        except Exception as e:
            logger.error(f"An error occurred during cleanup: {e}")

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
                               scheduler_settings.COLLECT_DAILY_METRICS_MINUTE),
            self.schedule_task("cleanup_old_files",
                               scheduler_settings.CLEANUP_OLD_FILES_HOUR,
                               scheduler_settings.CLEANUP_OLD_FILES_MINUTE)
        ]
        await asyncio.gather(*tasks)

scheduler = ReportScheduler()

def start_scheduler():
    asyncio.run(scheduler.start())

if __name__ == "__main__":
    start_scheduler()