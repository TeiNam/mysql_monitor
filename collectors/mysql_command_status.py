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

DESIRED_COMMANDS = [
    'Com_select', 'Com_delete', 'Com_delete_multi',
    'Com_insert', 'Com_insert_select', 'Com_replace',
    'Com_replace_select', 'Com_update', 'Com_update_multi',
    'Com_flush', 'Com_kill', 'Com_purge', 'Com_admin_commands',
    'Com_commit', 'Com_begin', 'Com_rollback'
]

class MySQLCommandStatusMonitor:
    def __init__(self, mysql_connector: MySQLConnector):
        self.mongodb = None
        self.status_collection = None
        self.mysql_connector = mysql_connector
        self._stop_event = asyncio.Event()

    async def stop(self):
        self._stop_event.set()
        logger.info("Stopping MySQLCommandStatusMonitor")

    async def initialize(self):
        try:
            self.mongodb = await MongoDBConnector.get_database()
            self.status_collection = self.mongodb[mongo_settings.MONGO_COM_STATUS_COLLECTION]
            logger.info("MongoDB connection initialized successfully for MySQLCommandStatusMonitor")
        except Exception as e:
            logger.error(f"Failed to initialize MySQLCommandStatusMonitor: {e}")
            raise

    async def query_mysql_status(self, query: str, single_row: bool = False) -> Optional[Any]:
        try:
            result = await self.mysql_connector.execute_query(query)
            if single_row:
                return int(result[0]['Value']) if result else 0
            else:
                return {row['Variable_name']: row['Value'] for row in result}
        except Exception as e:
            logger.error(f"Failed to execute query for {self.mysql_connector.instance_name}: {e}")
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

    async def save_mysql_command_status_to_mongodb(self, command_status: Dict[str, Dict[str, Any]]):
        try:
            document = {
                'timestamp': datetime.now(pytz.utc),
                'instance_name': self.mysql_connector.instance_name,
                'command_status': command_status
            }
            result = await self.status_collection.insert_one(document)
            logger.info(f"Saved command status for {self.mysql_connector.instance_name}. MongoDB _id: {result.inserted_id}")
        except Exception as e:
            logger.error(f"Failed to save command status for {self.mysql_connector.instance_name} to MongoDB: {e}")
            raise

    async def query_instance_and_save_to_db(self):
        try:
            uptime = await self.query_mysql_status("SHOW GLOBAL STATUS LIKE 'Uptime';", True)
            if uptime is None:
                logger.warning(f"Could not retrieve uptime for {self.mysql_connector.instance_name}")
                return

            raw_status = await self.query_mysql_status("SHOW GLOBAL STATUS LIKE 'Com_%';")
            if raw_status is None:
                logger.warning(f"Could not retrieve global status for {self.mysql_connector.instance_name}")
                return

            processed_status = self.process_global_status(raw_status, uptime)
            await self.save_mysql_command_status_to_mongodb(processed_status)
            logger.info(f"Successfully processed and saved command status for {self.mysql_connector.instance_name}")
        except Exception as e:
            logger.error(f"Failed to process command status for {self.mysql_connector.instance_name}: {e}")

    async def run(self):
        try:
            logger.info(f"Starting command status collection for {self.mysql_connector.instance_name}")
            await self.query_instance_and_save_to_db()
            logger.info(f"Command status collection completed for {self.mysql_connector.instance_name}")
        except Exception as e:
            logger.error(f"An error occurred during command status collection for {self.mysql_connector.instance_name}: {e}")