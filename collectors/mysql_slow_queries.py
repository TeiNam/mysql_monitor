import asyncio
import pytz
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
from modules.mongodb_connector import MongoDBConnector
from modules.mysql_connector import MySQLConnector
from configs.mongo_conf import mongo_settings
import logging
from configs.log_conf import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

EXEC_TIME = 2

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
    def __init__(self, mysql_connector: MySQLConnector):
        self.pid_time_cache: Dict[int, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
        self.mysql_connector = mysql_connector
        self._stop_event = asyncio.Event()
        self.mongodb = None
        self.collection = None

    async def stop(self):
        self._stop_event.set()
        logger.info(f"Stopping SlowQueryMonitor for {self.mysql_connector.instance_name}")

    async def initialize(self):
        self.mongodb = await MongoDBConnector.get_database()
        self.collection = self.mongodb[mongo_settings.MONGO_SLOW_LOG_COLLECTION]
        logger.info(f"Initialized SlowQueryMonitor for {self.mysql_connector.instance_name}")

    async def query_mysql_instance(self) -> None:
        try:
            sql_query = """SELECT `ID`, `DB`, `USER`, `HOST`, `TIME`, `INFO`
                            FROM `information_schema`.`PROCESSLIST`
                            WHERE info IS NOT NULL
                            AND DB not in ('information_schema', 'mysql', 'performance_schema')
                            AND USER not in ('monitor', 'rdsadmin', 'system user')
                            ORDER BY `TIME` DESC"""

            result = await self.mysql_connector.execute_query(sql_query)

            current_pids = set()
            for row in result:
                await self.process_query_result(row, current_pids)

            await self.handle_finished_queries(current_pids)

        except Exception as e:
            self.logger.error(f"Error querying MySQL instance {self.mysql_connector.instance_name}: {e}")

    async def process_query_result(self, row: Dict[str, Any], current_pids: set) -> None:
        pid, db, user, host, time, info = row['ID'], row['DB'], row['USER'], row['HOST'], row['TIME'], row['INFO']
        current_pids.add(pid)

        if time >= EXEC_TIME:
            cache_data = self.pid_time_cache.setdefault(pid, {'max_time': 0})
            cache_data['max_time'] = max(cache_data['max_time'], time)

            if 'start' not in cache_data:
                utc_now = datetime.now(pytz.utc)
                utc_start_timestamp = int((utc_now - timedelta(seconds=EXEC_TIME)).timestamp())
                utc_start_datetime = datetime.fromtimestamp(utc_start_timestamp, pytz.utc)
                cache_data['start'] = utc_start_datetime

            info_cleaned = re.sub(' +', ' ', info).encode('utf-8', 'ignore').decode('utf-8')
            info_cleaned = re.sub(r'[\n\t\r]+', ' ', info_cleaned).strip()

            cache_data['details'] = QueryDetails(
                instance=self.mysql_connector.instance_name,
                db=db,
                pid=pid,
                user=user,
                host=host,
                time=time,
                sql_text=info_cleaned,
                start=cache_data['start']
            )

    async def handle_finished_queries(self, current_pids: set) -> None:
        for pid, cache_data in list(self.pid_time_cache.items()):
            if pid not in current_pids:
                data_to_insert = vars(cache_data['details'])
                data_to_insert['time'] = cache_data['max_time']
                data_to_insert['end'] = datetime.now(pytz.utc)

                existing_query = await self.collection.find_one({
                    'pid': data_to_insert['pid'],
                    'instance': data_to_insert['instance'],
                    'db': data_to_insert['db'],
                    'start': data_to_insert['start']
                })

                if not existing_query:
                    await self.collection.insert_one(data_to_insert)
                    self.logger.info(f"Inserted slow query data: instance={self.mysql_connector.instance_name}, DB={data_to_insert['db']}, PID={pid}, execution_time={data_to_insert['time']}s")

                del self.pid_time_cache[pid]

    async def run_mysql_slow_queries(self) -> None:
        try:
            self.logger.info(f"Starting slow query monitoring for {self.mysql_connector.instance_name}")

            while not self._stop_event.is_set():
                await self.query_mysql_instance()
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info(f"Slow query monitoring task was cancelled for {self.mysql_connector.instance_name}")
        except Exception as e:
            self.logger.error(f"An error occurred in slow query monitoring for {self.mysql_connector.instance_name}: {e}")
        finally:
            self.logger.info(f"Slow query monitoring stopped for {self.mysql_connector.instance_name}")