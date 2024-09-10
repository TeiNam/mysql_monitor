import sys
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import asyncio
from modules.mongodb_connector import MongoDBConnector
import logging
from configs.rds_instance_conf import AWS_REGIONS, AWS_RDS_INSTANCE_ALL_STAT_COLLECTION

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

def get_account_id():
    sts_client = boto3.client('sts')
    try:
        return sts_client.get_caller_identity()["Account"]
    except ClientError as e:
        logger.error(f"Error getting AWS account ID: {e}")
        return None

async def get_rds_instances():
    instances = []
    for region in AWS_REGIONS:
        try:
            rds = boto3.client('rds', region_name=region)
            paginator = rds.get_paginator('describe_db_instances')
            for page in paginator.paginate():
                for instance in page['DBInstances']:
                    instance_data = {
                        'Region': region,
                        'DBInstanceIdentifier': instance.get('DBInstanceIdentifier'),
                        'DBInstanceClass': instance.get('DBInstanceClass'),
                        'Engine': instance.get('Engine'),
                        'EngineVersion': instance.get('EngineVersion'),
                        'DBInstanceStatus': instance.get('DBInstanceStatus'),
                        'MasterUsername': instance.get('MasterUsername'),
                        'AllocatedStorage': instance.get('AllocatedStorage'),
                        'AvailabilityZone': instance.get('AvailabilityZone'),
                        'MultiAZ': instance.get('MultiAZ'),
                        'StorageType': instance.get('StorageType'),
                        'InstanceCreateTime': instance.get('InstanceCreateTime').isoformat() if instance.get('InstanceCreateTime') else None,
                        'Tags': {tag['Key']: tag['Value'] for tag in instance.get('TagList', [])}
                    }
                    instances.append(instance_data)
        except ClientError as e:
            logger.error(f"Error fetching RDS instances in region {region}: {e}")
    return instances

async def save_to_mongodb(instances, account_id):
    db = await MongoDBConnector.get_database()
    collection = db[AWS_RDS_INSTANCE_ALL_STAT_COLLECTION]

    data = {
        'timestamp': datetime.now(),
        'account_id': account_id,
        'total_instances': len(instances),
        'instances': instances
    }

    await collection.insert_one(data)
    logger.info(f"Saved {len(instances)} RDS instances for account {account_id} to MongoDB collection: {AWS_RDS_INSTANCE_ALL_STAT_COLLECTION}")

async def run_rds_instance_collector():
    await MongoDBConnector.initialize()

    account_id = get_account_id()
    if not account_id:
        logger.error("Failed to get AWS account ID. Exiting.")
        return

    instances = await get_rds_instances()
    await save_to_mongodb(instances, account_id)

    await MongoDBConnector.close()

if __name__ == "__main__":
    asyncio.run(run_rds_instance_collector())