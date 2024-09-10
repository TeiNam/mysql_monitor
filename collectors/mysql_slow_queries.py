import asyncio
import pytz
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from modules.mongodb_connector import MongoDBConnector
from modules.mysql_connector import mysql_connector
from modules.load_instance import load_instances_from_mongodb
from configs.mongo_conf import mongo_settings
from configs.mysql_conf import EXEC_TIME
import logging
from configs.log_conf import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

@dataclass
class QueryDetails:
    instance: str
    db: str
    pid: int
    user: str
    host: str
    time: int
    sql_text: str
    start: datetime
    end: Optional[datetime] = None

class SlowQueryMonitor:
    def __init__(self):
        self.pid_time_cache: Dict[tuple, Dict[str, Any]] = {}
        self.ignore_instance_names: List[str] = []
        self.logger = logging.getLogger(__name__)

    async def query_mysql_instance(self, instance_name: str, collection: Any) -> None:
        try:
            if instance_name in self.ignore_instance_names:
                return

            current_pids = set()
            sql_query = """SELECT `ID`, `DB`, `USER`, `HOST`, `TIME`, `INFO`
                            FROM `information_schema`.`PROCESSLIST`
                            WHERE info IS NOT NULL
                            AND DB not in ('information_schema', 'mysql', 'performance_schema')
                            AND USER not in ('monitor', 'rdsadmin', 'system user')
                            ORDER BY `TIME` DESC"""

            result = await mysql_connector.execute_query(instance_name, sql_query)

            for row in result:
                await self.process_query_result(instance_name, row, current_pids)

            await self.handle_finished_queries(instance_name, current_pids, collection)

        except Exception as e:
            self.logger.error(f"Error querying instance {instance_name}: {e}")

    async def process_query_result(self, instance_name: str, row: Dict[str, Any], current_pids: set) -> None:
        pid, db, user, host, time, info = row['ID'], row['DB'], row['USER'], row['HOST'], row['TIME'], row['INFO']
        current_pids.add(pid)

        if time >= EXEC_TIME:
            cache_data = self.pid_time_cache.setdefault((instance_name, pid), {'max_time': 0})
            cache_data['max_time'] = max(cache_data['max_time'], time)

            if 'start' not in cache_data:
                utc_now = datetime.now(pytz.utc)
                utc_start_timestamp = int((utc_now - timedelta(seconds=EXEC_TIME)).timestamp())
                utc_start_datetime = datetime.fromtimestamp(utc_start_timestamp, pytz.utc)
                cache_data['start'] = utc_start_datetime

            info_cleaned = re.sub(' +', ' ', info).encode('utf-8', 'ignore').decode('utf-8')
            info_cleaned = re.sub(r'[\n\t\r]+', ' ', info_cleaned).strip()

            cache_data['details'] = QueryDetails(
                instance=instance_name,  # 인스턴스 이름 그대로 유지
                db=db,  # 데이터베이스 이름 그대로 유지
                pid=pid,
                user=user,
                host=host,
                time=time,
                sql_text=info_cleaned,
                start=cache_data['start']
            )

    async def handle_finished_queries(self, instance_name: str, current_pids: set, collection: Any) -> None:
        for (instance, pid), cache_data in list(self.pid_time_cache.items()):
            if pid not in current_pids and instance == instance_name:
                data_to_insert = vars(cache_data['details'])
                data_to_insert['time'] = cache_data['max_time']
                data_to_insert['end'] = datetime.now(pytz.utc)

                # 대소문자를 구분하여 검색
                existing_query = await collection.find_one({
                    'pid': data_to_insert['pid'],
                    'instance': data_to_insert['instance'],
                    'db': data_to_insert['db'],
                    'start': data_to_insert['start']
                })

                if not existing_query:
                    await collection.insert_one(data_to_insert)
                    self.logger.info(f"Inserted slow query data: instance={instance_name}, DB={data_to_insert['db']}, PID={pid}, execution_time={data_to_insert['time']}s")

                del self.pid_time_cache[(instance, pid)]

    async def run_mysql_slow_queries(self) -> None:
        try:
            await MongoDBConnector.initialize()
            db = await MongoDBConnector.get_database()
            collection = db[mongo_settings.MONGO_SLOW_LOG_COLLECTION]

            instances = await load_instances_from_mongodb()
            self.logger.info(f"Starting slow query monitoring for {len(instances)} MySQL instances")

            while True:
                tasks = []
                for instance_data in instances:
                    instance_name = instance_data["instance_name"]
                    if instance_name not in self.ignore_instance_names:
                        tasks.append(self.query_mysql_instance(instance_name, collection))

                if tasks:
                    await asyncio.gather(*tasks)

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("Slow query monitoring task was cancelled")
        except Exception as e:
            self.logger.error(f"An error occurred in slow query monitoring: {e}")
        finally:
            await mysql_connector.close_all_pools()
            self.logger.info("Slow query monitoring stopped, all resources released")

if __name__ == '__main__':
    monitor = SlowQueryMonitor()
    asyncio.run(monitor.run_mysql_slow_queries())