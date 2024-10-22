import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from fastapi import HTTPException
from typing import Callable, Dict, Any
import httpx
import os
import shutil

from apis.routes.slow_query_stat import get_weekly_statistics
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
            "cleanup_old_files": self.cleanup_old_files,
            "weekly_slow_query_report": self.weekly_slow_query_report  # 새로운 태스크 추가
        }
        self.weekly_tasks = {"weekly_slow_query_report"}  # 주간 태스크 집합 추가

    async def schedule_task(self, task_name: str, hour: int, minute: int):
        while True:
            # 현재 시간을 KST로 가져오기
            now = datetime.now(kst)

            # 다음 실행 시간을 KST로 설정
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if task_name in self.weekly_tasks:
                # 현재 요일이 월요일(0)이고 지정된 시간이 지나지 않았다면 오늘
                # 그렇지 않다면 다음 월요일로 설정
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0 and now.time() < datetime.strptime(f"{hour}:{minute}", "%H:%M").time():
                    pass  # 오늘이 월요일이고 아직 시간이 안됐으면 그대로 둠
                else:
                    if days_until_monday == 0:  # 월요일인데 시간이 지난 경우
                        days_until_monday = 7
                    next_run += timedelta(days=days_until_monday)
            else:
                # 일일 태스크의 경우
                if next_run <= now:
                    next_run += timedelta(days=1)

            # KST 기준으로 대기 시간 계산
            wait_seconds = (next_run - now).total_seconds()

            logger.info(f"Next run of {task_name} scheduled at {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')} KST")
            logger.info(f"Current time is {now.strftime('%Y-%m-%d %H:%M:%S %Z')} KST")
            logger.info(f"Waiting for {wait_seconds} seconds")

            await asyncio.sleep(wait_seconds)

            # 실행 시점에서 다시 한번 요일 체크 (주간 태스크의 경우)
            current_time = datetime.now(kst)
            if task_name in self.weekly_tasks and current_time.weekday() != 0:  # 월요일이 아니면 스킵
                continue

            await self.run_task(task_name)

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

            # 주간 태스크인 경우 다음 월요일로 설정
            if task_name in self.weekly_tasks:
                # 현재 요일이 월요일(0)이고 지정된 시간이 지나지 않았다면 오늘
                # 그렇지 않다면 다음 월요일로 설정
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0 and now.time() < datetime.strptime(f"{hour}:{minute}", "%H:%M").time():
                    pass  # 오늘이 월요일이고 아직 시간이 안됐으면 그대로 둠
                else:
                    if days_until_monday == 0:  # 월요일인데 시간이 지난 경우
                        days_until_monday = 7
                    next_run += timedelta(days=days_until_monday)
            else:
                # 일일 태스크의 경우 기존 로직 유지
                if next_run <= now:
                    next_run += timedelta(days=1)

            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Next run of {task_name} scheduled at {next_run}")

            await asyncio.sleep(wait_seconds)
            if task_name in self.weekly_tasks and now.weekday() != 0:  # 월요일이 아니면 스킵
                continue
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

    async def start(self):
        tasks = [
            self.schedule_task("collect_daily_metrics",
                               scheduler_settings.COLLECT_DAILY_METRICS_HOUR,
                               scheduler_settings.COLLECT_DAILY_METRICS_MINUTE),
            self.schedule_task("cleanup_old_files",
                               scheduler_settings.CLEANUP_OLD_FILES_HOUR,
                               scheduler_settings.CLEANUP_OLD_FILES_MINUTE),
            self.schedule_task("weekly_slow_query_report", 10, 0)  # 매주 월요일 오전 10시 (KST)
        ]
        logger.info("Starting scheduler with KST timezone")
        await asyncio.gather(*tasks)

scheduler = ReportScheduler()

def start_scheduler():
    asyncio.run(scheduler.start())

if __name__ == "__main__":
    start_scheduler()

