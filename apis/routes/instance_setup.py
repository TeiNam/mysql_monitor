from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from modules.crypto_utils import encrypt_password
from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class SlowMySQLInstance(BaseModel):
    environment: str = Field(default="DEV")
    db_type: str = Field(default="MySQL")
    cluster_name: Optional[str] = Field(default=None)
    instance_name: str
    host: str
    port: Optional[int] = Field(default=3306)
    region: str = Field(default="ap-northeast-2")
    user: str
    password: str
    db: Optional[str] = Field(default="information_schema")
    account: str

class SlowMySQLInstanceResponse(BaseModel):
    environment: str
    db_type: str
    cluster_name: Optional[str]
    instance_name: str
    host: str
    port: int
    region: str
    user: str
    db: Optional[str]
    account: Optional[str] = None  # account 필드를 옵셔널로 변경

@router.get("/list_slow_instances/", response_model=List[SlowMySQLInstanceResponse])
async def list_slow_instances():
    try:
        db = await MongoDBConnector.get_database()
        collection = db[mongo_settings.MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION]
        instances = await collection.find({}, {'_id': 0, 'password': 0}).to_list(length=None)
        return instances
    except Exception as e:
        logger.error(f"Error in list_slow_instances: {str(e)}")
        return []

@router.post("/add_slow_instance/", status_code=201)
async def add_slow_instance(slow_mysql_instance: SlowMySQLInstance):
    encrypted_password = encrypt_password(slow_mysql_instance.password)
    db = await MongoDBConnector.get_database()
    collection = db[mongo_settings.MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION]

    instance_data = {
        "environment": slow_mysql_instance.environment,
        "db_type": slow_mysql_instance.db_type,
        "cluster_name": slow_mysql_instance.cluster_name,
        "instance_name": slow_mysql_instance.instance_name,
        "host": slow_mysql_instance.host,
        "port": slow_mysql_instance.port or 3306,
        "region": slow_mysql_instance.region or "ap-northeast-2",
        "user": slow_mysql_instance.user,
        "password": encrypted_password,
        "db": slow_mysql_instance.db,
        "account": slow_mysql_instance.account
    }

    result = await collection.update_one(
        {"instance_name": slow_mysql_instance.instance_name},
        {"$set": instance_data},
        upsert=True
    )

    if result.matched_count:
        return {"message": "Slow MySQL Instance updated successfully"}
    else:
        return {"message": "New Slow MySQL Instance inserted successfully"}

@router.delete("/delete_slow_instance/")
async def delete_slow_instance(instance_name: str):
    db = await MongoDBConnector.get_database()
    collection = db[mongo_settings.MONGO_GET_SLOW_MYSQL_INSTANCE_COLLECTION]
    result = await collection.delete_one({"instance_name": instance_name})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Slow MySQL Instance not found")

    return {"message": "Slow MySQL Instance deleted successfully"}