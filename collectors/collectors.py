import asyncio
import pytz
import logging
from datetime import datetime, timedelta
from .mysql_slow_queries import SlowQueryMonitor
from .mysql_command_status import MySQLCommandStatusMonitor
from .rds_instance_status import run_rds_instance_collector
from .mysql_disk_status import MySQLDiskStatusMonitor
from configs.log_conf import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

def get_seconds_until_next_run(hour, minute):
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

async def run_daily_at_time(task_func, hour, minute):
    while True:
        seconds_until_next_run = get_seconds_until_next_run(hour, minute)
        await asyncio.sleep(seconds_until_next_run)
        logger.info(f"Running scheduled task: {task_func.__name__}")
        try:
            await task_func()
        except Exception as e:
            logger.error(f"Error in {task_func.__name__}: {e}")

async def run_periodically(task_func, interval_seconds):
    while True:
        try:
            await task_func()
        except Exception as e:
            logger.error(f"Error in {task_func.__name__}: {e}")
        await asyncio.sleep(interval_seconds)

async def run_with_restart(task_func):
    while True:
        try:
            await task_func()
        except Exception as e:
            logger.error(f"Error in {task_func.__name__}: {e}")
            logger.info(f"Restarting task in 5 seconds...")
            await asyncio.sleep(5)  # 5초 후 재시작

async def run_slow_queries():
    monitor = SlowQueryMonitor()
    await monitor.run_mysql_slow_queries()

async def run_command_status():
    monitor = MySQLCommandStatusMonitor()
    await monitor.run()

async def run_disk_status():
    monitor = MySQLDiskStatusMonitor()
    await monitor.run()


async def main():
    # SlowQueryMonitor는 예외 발생 시 재시작
    slow_queries_task = asyncio.create_task(run_with_restart(run_slow_queries))

    # MySQLCommandStatusMonitor를 매일 오전 9:00에 실행
    command_status_task = asyncio.create_task(run_daily_at_time(run_command_status, 9, 0))

    # RDS Instance Collector를 매일 오전 9시에 실행
    rds_instance_task = asyncio.create_task(run_daily_at_time(run_rds_instance_collector, 9, 0))

    # MySQLDiskStatusMonitor 10분 주기로 수집
    disk_usage_task = asyncio.create_task(run_periodically(run_disk_status, 600))

    # 예외가 발생해도 다른 태스크에 영향을 주지 않도록 함
    await asyncio.gather(
        slow_queries_task,
        command_status_task,
        disk_usage_task,
        rds_instance_task,
        return_exceptions=True
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"A critical error occurred: {e}")