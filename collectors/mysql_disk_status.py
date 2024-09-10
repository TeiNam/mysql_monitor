import asyncio
import pytz
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from modules.load_instance import load_instances_from_mongodb
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

@dataclass
class MySQLMetric:
    name: str
    value: int
    avg_for_hours: float
    avg_for_seconds: float


class MySQLDiskStatusMonitor:
    def __init__(self):
        self.mongodb = None
        self.status_collection = None
        self.mysql_connector = MySQLConnector("disk_status")

    async def initialize(self):
        await MongoDBConnector.initialize()
        self.mongodb = await MongoDBConnector.get_database()
        self.status_collection = self.mongodb[mongo_settings.MONGO_DISK_USAGE_COLLECTION]

        instances = await load_instances_from_mongodb()
        for instance in instances:
            await self.mysql_connector.create_pool(instance, pool_size=1)

    async def execute_mysql_query(self, instance_name: str, query: str, single_row: bool = False) -> Optional[Any]:
        try:
            result = await self.mysql_connector.execute_query(query)
            if single_row:
                return int(result[0]['Value']) if result else 0
            else:
                return {row['Variable_name']: row['Value'] for row in result}
        except Exception as e:
            logger.error(f"Failed to execute query for {instance_name}: {e}")
            return None

    def process_metrics(self, data: Dict[str, str], uptime: int) -> List[MySQLMetric]:
        processed_data = []
        for key, value in data.items():
            if key in MYSQL_METRICS and value != '0':
                value = int(value)
                avg_for_hours = round(value / max(uptime / 3600, 1), 2)
                avg_for_seconds = round(value / max(uptime, 1), 2)
                processed_data.append(MySQLMetric(key, value, avg_for_hours, avg_for_seconds))
        return sorted(processed_data, key=lambda x: x.value, reverse=True)

    async def store_metrics_to_mongodb(self, instance_name: str, metrics: List[MySQLMetric]):
        document = {
            'timestamp': datetime.now(pytz.utc),
            'instance_name': instance_name,
            'metrics': [metric.__dict__ for metric in metrics]
        }
        await self.status_collection.insert_one(document)

    async def fetch_and_save_instance_data(self, instance: Dict[str, Any]):
        instance_name = instance['instance_name']
        uptime = await self.execute_mysql_query(instance_name, "SHOW GLOBAL STATUS LIKE 'Uptime';", True)
        if uptime is None:
            logger.warning(f"Could not retrieve uptime for {instance_name}")
            return

        raw_status = {}
        for metric in MYSQL_METRICS:
            query = f"SHOW GLOBAL STATUS LIKE '{metric}';"
            result = await self.execute_mysql_query(instance_name, query)
            if result:
                raw_status.update(result)

        if not raw_status:
            logger.warning(f"Could not retrieve global status for {instance_name}")
            return

        processed_metrics = self.process_metrics(raw_status, uptime)
        await self.store_metrics_to_mongodb(instance_name, processed_metrics)

    async def run(self):
        try:
            await self.initialize()
            instances = await load_instances_from_mongodb()

            for instance in instances:
                await self.mysql_connector.create_pool(instance, pool_size=1)

            tasks = [self.fetch_and_save_instance_data(instance) for instance in instances]
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            await self.mysql_connector.close_pool()

async def run_selected_metrics_status():
    monitor = MySQLDiskStatusMonitor()
    await monitor.run()


if __name__ == '__main__':
    asyncio.run(run_selected_metrics_status())