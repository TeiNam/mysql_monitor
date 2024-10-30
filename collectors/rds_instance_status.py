import sys
import os
import json
import boto3
import asyncio
import logging
from typing import List, Optional, Any
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()  # .env 파일 로드

# 로깅 설정
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# MongoDB 설정
MONGODB_URI = os.getenv('MONGODB_URI')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME')
AWS_RDS_INSTANCE_ALL_STAT_COLLECTION = 'aws_rds_instance_all_stat'

# AWS 설정
AWS_REGIONS_STR = os.getenv('AWS_REGIONS')
if not AWS_REGIONS_STR:
    raise ValueError("AWS_REGIONS is not set in the environment variables.")
try:
    AWS_REGIONS = json.loads(AWS_REGIONS_STR)
except json.JSONDecodeError:
    raise ValueError("AWS_REGIONS is not a valid JSON string.")

# 시간 유틸리티 함수
KST = timezone(timedelta(hours=9))
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
KST_DATETIME_FORMAT = f"{DATETIME_FORMAT} KST"


def get_kst_time() -> str:
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(KST).strftime(KST_DATETIME_FORMAT)


def convert_utc_to_kst(utc_time: Optional[datetime]) -> Optional[datetime]:
    if utc_time is None:
        return None
    return utc_time.replace(tzinfo=timezone.utc).astimezone(KST)


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.strftime(KST_DATETIME_FORMAT)


# AWS 세션 생성 함수
def create_sts_session(account_id: str, role_name: str):
    sts_client = boto3.client('sts')
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    try:
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"AssumeRoleSession-{account_id}"
        )
        credentials = response['Credentials']

        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
    except Exception as e:
        logger.error(f"Error assuming role for account {account_id}: {e}")
        return None


# RDS 인스턴스 정보 수집 함수
async def get_rds_instances(session: Any, account_id: str) -> List[dict]:
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
                        'Endpoint': {
                            'Address': instance.get('Endpoint', {}).get('Address'),
                            'Port': instance.get('Endpoint', {}).get('Port')
                        } if instance.get('Endpoint') else None,
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


# MongoDB에 데이터 저장 함수
async def save_to_mongodb(instances: List[dict], account_id: str):
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]
    collection = db[AWS_RDS_INSTANCE_ALL_STAT_COLLECTION]

    data = {
        'timestamp': get_kst_time(),
        'account_id': account_id,
        'total_instances': len(instances),
        'instances': instances
    }

    try:
        await collection.insert_one(data)
        logger.info(f"Saved {len(instances)} RDS instances for account {account_id}")
    except Exception as e:
        logger.error(f"Error saving to MongoDB for account {account_id}: {e}")
    finally:
        client.close()


# RDS 인스턴스 수집 실행 함수
async def run_rds_instance_collector(accounts: List[str]):
    for account in accounts:
        try:
            account_id = str(account).strip()
            logger.info(f"Processing account: {account_id}")

            sts_session = create_sts_session(account_id, 'mgmt-db-monitoring-assumerole')

            if sts_session:
                instances = await get_rds_instances(sts_session, account_id)
                if instances:
                    await save_to_mongodb(instances, account_id)
                else:
                    logger.info(f"No RDS instances found for account {account_id}")
            else:
                logger.error(f"Failed to create session for account {account_id}")

        except Exception as e:
            logger.exception(f"Unexpected error processing account {account_id}: {str(e)}")


# 메인 함수
async def main():
    accounts = ['488659748805', '578868370045', '790631726648', '732250966717', '518026839586', '897374448634',
                '708010261224', '058264293746', '637423179433']
    await run_rds_instance_collector(accounts)


if __name__ == '__main__':
    asyncio.run(main())