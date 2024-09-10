import asyncio
import pytz
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from modules.load_instance import load_instances_from_mongodb
from modules.mongodb_connector import MongoDBConnector
from modules.mysql_connector import MySQLConnector
from configs.mongo_conf import mongo_settings
from configs.log_conf import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# 모듈 내부에 DESIRED_COMMANDS 정의
DESIRED_COMMANDS = [
    'Com_select', 'Com_delete', 'Com_delete_multi',
    'Com_insert', 'Com_insert_select', 'Com_replace',
    'Com_replace_select', 'Com_update', 'Com_update_multi',
    'Com_flush', 'Com_kill', 'Com_purge', 'Com_admin_commands',
    'Com_commit', 'Com_begin', 'Com_rollback'
]


class MySQLCommandStatusMonitor:
    def __init__(self):
        self.mongodb = None
        self.status_collection = None
        self.mysql_connectors: Dict[str, MySQLConnector] = {}

    async def initialize(self):
        await MongoDBConnector.initialize()
        self.mongodb = await MongoDBConnector.get_database()
        self.status_collection = self.mongodb[mongo_settings.MONGO_COM_STATUS_COLLECTION]

        instances = await load_instances_from_mongodb()
        for instance in instances:
            instance_name = instance['instance_name']
            self.mysql_connectors[instance_name] = MySQLConnector("command_status")
            await self.mysql_connectors[instance_name].create_pool(instance, pool_size=1)

    async def query_mysql_status(self, instance_name: str, query: str, single_row: bool = False) -> Optional[Any]:
        try:
            result = await self.mysql_connectors[instance_name].execute_query(instance_name, query)
            if single_row:
                return int(result[0]['Value']) if result else 0
            else:
                return {row['Variable_name']: row['Value'] for row in result}
        except Exception as e:
            logger.error(f"Failed to execute query for {instance_name}: {e}")
            return None

    def process_global_status(self, data: Dict[str, str], uptime: int) -> Dict[str, Dict[str, Any]]:
        processed_data = {}
        total_sum = sum(int(value) for key, value in data.items() if key in DESIRED_COMMANDS and value != '0')

        for key, value in data.items():
            if key in DESIRED_COMMANDS and value != '0':
                new_key = key[4:]
                value = int(value)
                avg_for_hours = round(value / max(uptime / 3600, 1), 2)
                avg_for_seconds = round(value / max(uptime, 1), 2)
                percentage = round((value / total_sum) * 100, 2) if total_sum > 0 else 0
                processed_data[new_key] = {
                    'total': value,
                    'avgForHours': avg_for_hours,
                    'avgForSeconds': avg_for_seconds,
                    'percentage': percentage
                }
        return dict(sorted(processed_data.items(), key=lambda item: item[1]['total'], reverse=True))

    async def save_mysql_command_status_to_mongodb(self, instance_name: str, command_status: Dict[str, Dict[str, Any]]):
        document = {
            'timestamp': datetime.now(pytz.utc),
            'instance_name': instance_name,
            'command_status': command_status
        }
        await self.status_collection.insert_one(document)

    async def query_instance_and_save_to_db(self, instance: Dict[str, Any]):
        instance_name = instance['instance_name']
        uptime = await self.query_mysql_status(instance_name, "SHOW GLOBAL STATUS LIKE 'Uptime';", True)
        if uptime is None:
            logger.warning(f"Could not retrieve uptime for {instance_name}")
            return
        raw_status = await self.query_mysql_status(instance_name, "SHOW GLOBAL STATUS LIKE 'Com_%';")
        if raw_status is None:
            logger.warning(f"Could not retrieve global status for {instance_name}")
            return
        processed_status = self.process_global_status(raw_status, uptime)
        await self.save_mysql_command_status_to_mongodb(instance_name, processed_status)

    async def run(self):
        try:
            await self.initialize()
            instances = await load_instances_from_mongodb()

            tasks = [self.query_instance_and_save_to_db(instance) for instance in instances]
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            for instance_name, connector in self.mysql_connectors.items():
                await connector.close_pool(instance_name)


mysql_command_status_monitor = MySQLCommandStatusMonitor()

async def run_mysql_command_status():
    await mysql_command_status_monitor.run()

if __name__ == '__main__':
    asyncio.run(run_mysql_command_status())