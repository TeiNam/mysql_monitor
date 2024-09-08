from modules.mongodb_connector import MongoDBConnector
from modules.mysql_connector import mysql_connector
from configs.mongo_conf import mongo_settings
import logging

logger = logging.getLogger(__name__)


async def load_instances_from_mongodb():
    try:
        mongodb = await MongoDBConnector.get_database()
        collection = mongodb[mongo_settings.MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION]
        instances = await collection.find().to_list(length=None)

        # Initialize MySQL connection pools for each instance
        for instance in instances:
            try:
                await mysql_connector.create_pool(instance)
                logger.info(f"Created MySQL connection pool for instance: {instance['instance_name']}")
            except Exception as e:
                logger.error(f"Failed to create MySQL connection pool for instance {instance['instance_name']}: {e}")

        return instances
    except Exception as e:
        logger.error(f"Failed to load instances from MongoDB: {e}")
        return []