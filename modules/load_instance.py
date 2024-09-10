from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings
import logging

logger = logging.getLogger(__name__)

cached_instances = None

async def load_instances_from_mongodb():
    global cached_instances
    if cached_instances is None:
        try:
            mongodb = await MongoDBConnector.get_database()
            collection = mongodb[mongo_settings.MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION]
            instances = await collection.find().to_list(length=None)

            cached_instances = []
            for instance in instances:
                processed_instance = {
                    'instance_name': instance['instance_name'],
                    'host': instance['host'],
                    'port': instance['port'],
                    'user': instance['user'],
                    'password': instance['password'],
                    'db': instance.get('db', '')
                }
                cached_instances.append(processed_instance)

            logger.info(f"Loaded {len(cached_instances)} MySQL instances from MongoDB")
        except Exception as e:
            logger.error(f"Failed to load instances from MongoDB: {e}")
            cached_instances = []

    return cached_instances

