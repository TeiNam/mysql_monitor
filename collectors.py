import asyncio
import pytz
from datetime import datetime, time, timedelta
from typing import Dict, Any, List
from collectors.mysql_slow_queries import SlowQueryMonitor
from collectors.mysql_command_status import MySQLCommandStatusMonitor
from collectors.mysql_disk_status import MySQLDiskStatusMonitor
from modules.load_instance import load_instances_from_mongodb
from modules.mongodb_connector import MongoDBConnector
from modules.mysql_connector import MySQLConnector
from configs.mongo_conf import mongo_settings
from configs.log_conf import LOG_LEVEL, LOG_FORMAT
import logging

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class DynamicCollectorManager:
    def __init__(self):
        self.instances: List[Dict[str, Any]] = []
        self.collectors: Dict[str, Dict[str, Any]] = {}
        self.mysql_connectors: Dict[str, MySQLConnector] = {}
        self.change_stream = None
        self._stop_event = asyncio.Event()

    async def stop(self):
        self._stop_event.set()
        logger.info("Stopping DynamicCollectorManager")
        for collectors in self.collectors.values():
            for collector in collectors.values():
                await collector.stop()
        for connector in self.mysql_connectors.values():
            await connector.close_pool()
        logger.info("DynamicCollectorManager stopped")

    async def initialize(self):
        try:
            await MongoDBConnector.initialize()
            self.mongodb = await MongoDBConnector.get_database()
            self.instances = await load_instances_from_mongodb()
            logger.info(f"Loaded {len(self.instances)} instances from MongoDB")

            for instance in self.instances:
                instance_name = instance['instance_name']
                self.mysql_connectors[instance_name] = MySQLConnector(instance_name)
                await self.mysql_connectors[instance_name].create_pool(instance, pool_size=1)

            await self.setup_collectors()
            logger.info("Collectors setup completed")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            raise

    async def setup_collectors(self):
        for instance in self.instances:
            await self.start_collector(instance)

    async def start_collector(self, instance):
        instance_name = instance['instance_name']
        if instance_name not in self.collectors:
            try:
                mysql_connector = self.mysql_connectors[instance_name]

                slow_query_monitor = SlowQueryMonitor(mysql_connector)
                command_status_monitor = MySQLCommandStatusMonitor(mysql_connector)
                disk_status_monitor = MySQLDiskStatusMonitor(mysql_connector)

                await slow_query_monitor.initialize()
                await command_status_monitor.initialize()
                await disk_status_monitor.initialize()

                self.collectors[instance_name] = {
                    'slow_query': slow_query_monitor,
                    'command_status': command_status_monitor,
                    'disk_status': disk_status_monitor
                }

                asyncio.create_task(self.run_slow_query_collector(instance_name))
                asyncio.create_task(self.run_command_status_collector(instance_name))
                asyncio.create_task(self.run_disk_status_collector(instance_name))
                logger.info(f"Started collectors for instance: {instance_name}")
            except Exception as e:
                logger.error(f"Error starting collectors for instance {instance_name}: {e}")

    async def stop_collector(self, instance_name):
        if instance_name in self.collectors:
            try:
                for collector in self.collectors[instance_name].values():
                    await collector.stop()
                del self.collectors[instance_name]
                await self.mysql_connectors[instance_name].close_pool()
                del self.mysql_connectors[instance_name]
                logger.info(f"Stopped collectors for instance: {instance_name}")
            except Exception as e:
                logger.error(f"Error stopping collectors for instance {instance_name}: {e}")

    async def run_slow_query_collector(self, instance_name):
        while not self._stop_event.is_set():
            try:
                await self.collectors[instance_name]['slow_query'].run_mysql_slow_queries()
            except Exception as e:
                logger.error(f"Error in slow query collector for {instance_name}: {e}")
                await asyncio.sleep(5)  # Wait before restarting

    async def run_at_specific_time(self, coroutine, target_time):
        while not self._stop_event.is_set():
            try:
                now = datetime.now(pytz.timezone('Asia/Seoul'))
                target = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
                if now > target:
                    target = target.replace(day=target.day + 1)
                wait_seconds = (target - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                await coroutine()
            except Exception as e:
                logger.error(f"Error in run_at_specific_time: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def run_command_status_collector(self, instance_name):
        async def run_command_status():
            try:
                await self.collectors[instance_name]['command_status'].run()
            except Exception as e:
                logger.error(f"Error in command status collector for {instance_name}: {e}")

        await self.run_at_specific_time(run_command_status, time(9, 0))  # Run at 9:00 AM KST

    async def run_disk_status_collector(self, instance_name):
        def get_next_run_time():
            now = datetime.now()
            minutes = now.minute
            if minutes < 15:
                next_minutes = 15
            elif minutes < 30:
                next_minutes = 30
            elif minutes < 45:
                next_minutes = 45
            else:
                next_minutes = 0
            next_run = now.replace(minute=next_minutes, second=0, microsecond=0)
            if next_minutes == 0:
                next_run += timedelta(hours=1)
            return next_run

        while not self._stop_event.is_set():
            try:
                next_run = get_next_run_time()
                now = datetime.now()
                wait_seconds = (next_run - now).total_seconds()

                logger.info(f"Next disk status collection for {instance_name} scheduled at {next_run}")
                await asyncio.sleep(wait_seconds)

                if self._stop_event.is_set():
                    break

                logger.info(f"Starting disk status collection for {instance_name}")
                await self.collectors[instance_name]['disk_status'].run()
                logger.info(f"Completed disk status collection for {instance_name}")

            except asyncio.CancelledError:
                logger.info(f"Disk status collector for {instance_name} was cancelled")
                break
            except Exception as e:
                logger.error(f"Error in disk status collector for {instance_name}: {e}")
                await asyncio.sleep(60)  # 오류 발생 시 1분 후 재시도

        logger.info(f"Disk status collector for {instance_name} is stopping")

    async def watch_instance_changes(self):
        try:
            collection = self.mongodb[mongo_settings.MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION]
            self.change_stream = collection.watch()
            async for change in self.change_stream:
                await self.handle_instance_change(change)
        except Exception as e:
            logger.error(f"Error in watch_instance_changes: {e}")

    async def handle_instance_change(self, change):
        try:
            operation_type = change['operationType']
            if operation_type in ['insert', 'update']:
                instance = change['fullDocument']
                processed_instance = self.process_instance(instance)
                self.instances = [inst for inst in self.instances if
                                  inst['instance_name'] != processed_instance['instance_name']]
                self.instances.append(processed_instance)
                await self.start_collector(processed_instance)
            elif operation_type == 'delete':
                instance_name = change['documentKey']['instance_name']
                self.instances = [inst for inst in self.instances if inst['instance_name'] != instance_name]
                await self.stop_collector(instance_name)
        except Exception as e:
            logger.error(f"Error handling instance change: {e}")

    def process_instance(self, instance):
        return {
            'instance_name': instance['instance_name'],
            'host': instance['host'],
            'port': instance['port'],
            'user': instance['user'],
            'password': instance['password'],
            'db': instance.get('db', ''),
            'account': instance.get('account', '')
        }

    async def refresh_instances(self):
        while not self._stop_event.is_set():
            try:
                new_instances = await load_instances_from_mongodb()
                current_instance_names = {inst['instance_name'] for inst in self.instances}
                new_instance_names = {inst['instance_name'] for inst in new_instances}

                for instance in new_instances:
                    if instance['instance_name'] not in current_instance_names:
                        self.instances.append(instance)
                        await self.start_collector(instance)

                for instance_name in current_instance_names - new_instance_names:
                    self.instances = [inst for inst in self.instances if inst['instance_name'] != instance_name]
                    await self.stop_collector(instance_name)

                logger.info(f"Refreshed instances. Current count: {len(self.instances)}")
            except Exception as e:
                logger.error(f"Error refreshing instances: {e}")
            finally:
                await asyncio.sleep(300)  # Refresh every 5 minutes

    async def run(self):
        try:
            await self.initialize()
            await asyncio.gather(
                self.watch_instance_changes(),
                self.refresh_instances(),
                return_exceptions=True
            )
        except Exception as e:
            logger.critical(f"Critical error in run method: {e}")


async def main():
    manager = DynamicCollectorManager()
    try:
        await manager.run()
    except KeyboardInterrupt:
        logger.info("Received stop signal, shutting down...")
    finally:
        await manager.stop()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All tasks have been canceled and completed.")


if __name__ == '__main__':
    asyncio.run(main())