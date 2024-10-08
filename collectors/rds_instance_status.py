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

def assume_role(account_id, role_name):
    sts_client = boto3.client('sts')
    role_arn = f'arn:aws:iam::{account_id}:role/{role_name}'
    try:
        assumed_role_object = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="AssumeRoleSession"
        )
        credentials = assumed_role_object['Credentials']
        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
    except ClientError as e:
        logger.error(f"Error assuming role for account {account_id}: {e}")
        return None

def create_sessions(account_ids, role_name):
    sessions = {}
    default_session = boto3.Session()
    for account_id in account_ids:
        try:
            if account_id == default_session.client('sts').get_caller_identity()['Account']:
                sessions[account_id] = default_session
                logger.info(f"Using default session for account: {account_id}")
            else:
                session = assume_role(account_id, role_name)
                if session:
                    sessions[account_id] = session
                    logger.info(f"Successfully assumed role for account: {account_id}")
        except Exception as e:
            logger.error(f"Error creating session for account {account_id}: {e}")
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


async def run_rds_instance_collector(account_ids, role_name):
    await MongoDBConnector.initialize()

    sessions = create_sessions(account_ids, role_name)

    for account_id, session in sessions.items():
        try:
            instances = await get_rds_instances(session, account_id)
            await save_to_mongodb(instances, account_id)

            logger.info(f"Completed data collection for account: {account_id}")
        except Exception as e:
            logger.error(f"Error processing account {account_id}: {e}")

    await MongoDBConnector.close()

if __name__ == "__main__":
    role_name = 'EC2RDSAccessRole'  # 각 계정에 생성한 역할의 이름
    account_ids = ['488659748805', '578868370045', '790631726648', '732250966717', '518026839586', '897374448634', '708010261224', '058264293746', '637423179433']
    asyncio.run(run_rds_instance_collector(account_ids, role_name))