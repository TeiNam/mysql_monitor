import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from fastapi import HTTPException
from typing import Callable, Dict, Any
import httpx

from apis.routes.slow_query_stat import get_weekly_statistics
from configs.scheduler_conf import SchedulerSettings
from configs.app_conf import app_settings
from .cleanup import ReportCleaner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler_settings = SchedulerSettings()
kst = pytz.timezone('Asia/Seoul')

class ReportScheduler:
    def __init__(self):
        self.tasks: Dict[str, Callable] = {
            "collect_daily_metrics": self.collect_daily_metrics,
            "cleanup_old_files": self.cleanup_old_files,
            "weekly_slow_query_report": self.weekly_slow_query_report
        }
        self.weekly_tasks = {"weekly_slow_query_report"}
        self.yearly_tasks = {"cleanup_old_files"}
        self.report_cleaner = ReportCleaner()

    async def schedule_task(self, task_name: str, hour: int, minute: int):
        while True:
            now = datetime.now(kst)
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if task_name in self.yearly_tasks:
                # 연간 태스크 (1월 3일)
                next_run = next_run.replace(month=1, day=3)
                if (now.month > 1 or (now.month == 1 and now.day > 3) or
                        (now.month == 1 and now.day == 3 and now.hour >= hour)):
                    next_run = next_run.replace(year=now.year + 1)

                logger.info(f"Yearly task {task_name} scheduled for {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            elif task_name in self.weekly_tasks:
                # 주간 태스크 (월요일)
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0 and now.time() < datetime.strptime(f"{hour}:{minute}", "%H:%M").time():
                    pass
                else:
                    if days_until_monday == 0:
                        days_until_monday = 7
                    next_run += timedelta(days=days_until_monday)
            else:
                # 일일 태스크
                if next_run <= now:
                    next_run += timedelta(days=1)

            wait_seconds = (next_run - now).total_seconds()

            logger.info(f"Next run of {task_name} scheduled at {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')} KST")
            logger.info(f"Current time is {now.strftime('%Y-%m-%d %H:%M:%S %Z')} KST")
            logger.info(f"Waiting for {wait_seconds} seconds")

            await asyncio.sleep(wait_seconds)

            # 실행 시점에서 조건 다시 확인
            current_time = datetime.now(kst)
            if (task_name in self.yearly_tasks and
                    (current_time.month != 1 or current_time.day != 3)):
                continue
            if (task_name in self.weekly_tasks and
                    current_time.weekday() != 0):
                continue

            await self.run_task(task_name)

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
        """클린업 실행"""
        try:
            await self.report_cleaner.cleanup()
            logger.info("Yearly cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during scheduled cleanup: {str(e)}")

    async def weekly_slow_query_report(self):
        try:
            # 현재 시간이 월요일인지 확인
            now = datetime.now(kst)
            if now.weekday() == 0:  # 0 = 월요일
                await get_weekly_statistics()
                logger.info("Weekly slow query report generated and sent successfully")
            else:
                logger.warning(f"Skipping weekly report as today is not Monday (current day: {now.strftime('%A')})")
        except Exception as e:
            logger.error(f"An error occurred while generating weekly slow query report: {e}")

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
            self.schedule_task("cleanup_old_files", 3, 0),  # 1월 3일 오전 3시
            self.schedule_task("weekly_slow_query_report", 10, 0)  # 매주 월요일 오전 10시
        ]
        logger.info("Starting scheduler with KST timezone")
        await asyncio.gather(*tasks)

scheduler = ReportScheduler()

def start_scheduler():
    asyncio.run(scheduler.start())

if __name__ == "__main__":
    start_scheduler()