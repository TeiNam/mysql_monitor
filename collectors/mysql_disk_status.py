import asyncio
import pytz
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from modules.mongodb_connector import MongoDBConnector
from modules.mysql_connector import MySQLConnector
from configs.mongo_conf import mongo_settings
from configs.log_conf import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

MYSQL_METRICS = [
    'Binlog_cache_use',
    'Binlog_cache_disk_use',
    'Created_tmp_tables',
    'Created_tmp_files',
    'Created_tmp_disk_tables'
]

class MySQLDiskStatusMonitor:
    def __init__(self, mysql_connector: MySQLConnector):
        self.mongodb = None
        self.status_collection = None
        self.mysql_connector = mysql_connector
        self._stop_event = asyncio.Event()

    async def stop(self):
        self._stop_event.set()
        logger.info(f"Stopping MySQLDiskStatusMonitor for {self.mysql_connector.instance_name}")

    async def initialize(self):
        self.mongodb = await MongoDBConnector.get_database()
        self.status_collection = self.mongodb[mongo_settings.MONGO_DISK_USAGE_COLLECTION]
        logger.info(f"Initialized MySQLDiskStatusMonitor for {self.mysql_connector.instance_name}")

    async def execute_mysql_query(self, query: str, single_row: bool = False) -> Optional[Any]:
        try:
            result = await self.mysql_connector.execute_query(query)
            if single_row:
                return int(result[0]['Value']) if result else 0
            else:
                return {row['Variable_name']: row['Value'] for row in result}
        except Exception as e:
            logger.error(f"Failed to execute query for {self.mysql_connector.instance_name}: {e}")
            return None

    def process_metrics(self, data: Dict[str, str], uptime: int) -> Dict[str, Dict[str, Any]]:
        processed_data = {}
        for key, value in data.items():
            if key in MYSQL_METRICS:
                value = int(value)
                avg_for_hours = round(value / max(uptime / 3600, 1), 2)
                avg_for_seconds = round(value / max(uptime, 1), 2)
                processed_data[key] = {
                    "total": value,
                    "avgForHours": avg_for_hours,
                    "avgForSeconds": avg_for_seconds
                }
        return processed_data

    async def store_metrics_to_mongodb(self, metrics: Dict[str, Dict[str, Any]]):
        document = {
            'timestamp': datetime.now(pytz.utc),
            'instance_name': self.mysql_connector.instance_name,
            'disk_status': metrics
        }
        await self.status_collection.insert_one(document)

    async def fetch_and_save_instance_data(self):
        uptime = await self.execute_mysql_query("SHOW GLOBAL STATUS LIKE 'Uptime';", True)
        if uptime is None:
            logger.warning(f"Could not retrieve uptime for {self.mysql_connector.instance_name}")
            return

        raw_status = {}
        for metric in MYSQL_METRICS:
            query = f"SHOW GLOBAL STATUS LIKE '{metric}';"
            result = await self.execute_mysql_query(query)
            if result:
                raw_status.update(result)

        if not raw_status:
            logger.warning(f"Could not retrieve global status for {self.mysql_connector.instance_name}")
            return

        processed_metrics = self.process_metrics(raw_status, uptime)
        await self.store_metrics_to_mongodb(processed_metrics)
        logger.info(f"Disk status data saved for {self.mysql_connector.instance_name}")

    async def run(self):
        try:
            logger.info(f"Starting disk status collection for {self.mysql_connector.instance_name}")
            await self.fetch_and_save_instance_data()
            logger.info(f"Disk status collection completed for {self.mysql_connector.instance_name}")
        except Exception as e:
            logger.error(f"An error occurred during disk status collection for {self.mysql_connector.instance_name}: {e}")