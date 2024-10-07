import sys
import os
import boto3
from botocore.exceptions import ClientError
import asyncio
from modules.mongodb_connector import MongoDBConnector
import logging
from configs.rds_instance_conf import AWS_REGIONS, AWS_RDS_INSTANCE_ALL_STAT_COLLECTION
from modules.time_utils import get_kst_time, convert_utc_to_kst, format_datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def create_sessions(profile_names):
    sessions = {}
    for profile in profile_names:
        try:
            session = boto3.Session(profile_name=profile)
            # SSO 자격 증명이 유효한지 확인
            sts = session.client('sts')
            sts.get_caller_identity()
            sessions[profile] = session
            logger.info(f"Successfully created session for profile: {profile}")
        except Exception as e:
            logger.error(f"Error creating session for profile {profile}: {e}")
    return sessions


async def get_rds_instances(session, account_id):
    instances = []
    for region in AWS_REGIONS:
        try:
            rds = session.client('rds', region_name=region)
            paginator = rds.get_paginator('describe_db_instances')
            for page in paginator.paginate():
                for instance in page['DBInstances']:
                    instance_data = {
                        'AccountId': account_id,
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
                        'InstanceCreateTime': format_datetime(convert_utc_to_kst(instance.get('InstanceCreateTime')))
                            if instance.get('InstanceCreateTime') else None,
                        'Tags': {tag['Key']: tag['Value'] for tag in instance.get('TagList', [])}
                    }
                    instances.append(instance_data)
        except ClientError as e:
            logger.error(f"Error fetching RDS instances in account {account_id}, region {region}: {e}")
    return instances


async def save_to_mongodb(instances, account_id):
    db = await MongoDBConnector.get_database()
    collection = db[AWS_RDS_INSTANCE_ALL_STAT_COLLECTION]

    data = {
        'timestamp': get_kst_time(),
        'account_id': account_id,
        'total_instances': len(instances),
        'instances': instances
    }

    await collection.insert_one(data)
    logger.info(
        f"Saved {len(instances)} RDS instances for account {account_id} to MongoDB collection: {AWS_RDS_INSTANCE_ALL_STAT_COLLECTION}")


async def run_rds_instance_collector(profile_names):
    await MongoDBConnector.initialize()

    sessions = create_sessions(profile_names)

    for profile, session in sessions.items():
        try:
            sts_client = session.client('sts')
            account_id = sts_client.get_caller_identity()['Account']

            instances = await get_rds_instances(session, account_id)
            await save_to_mongodb(instances, account_id)

            logger.info(f"Completed data collection for profile: {profile}, account: {account_id}")
        except Exception as e:
            logger.error(f"Error processing profile {profile}: {e}")

    await MongoDBConnector.close()


if __name__ == "__main__":
    sso_session_name = ''
    profile_names = []  # 사용할 프로필 이름들을 여기에 나열하세요
    asyncio.run(run_rds_instance_collector(profile_names))