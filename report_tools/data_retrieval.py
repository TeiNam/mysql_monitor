import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from functools import lru_cache
from typing import Dict, Any, List
from fastapi import HTTPException
from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings
from configs.report_conf import report_settings
import structlog

logger = structlog.get_logger()

def validate_instance_data(data: Dict[str, Any]) -> bool:
    required_keys = ['total_instances', 'dev_instances', 'prd_instances', 'account_count', 'region_count', 'accounts', 'regions', 'instance_classes']
    return all(key in data for key in required_keys)

def validate_prometheus_data(data: List[Dict[str, Any]]) -> bool:
    if not data:
        return False
    required_keys = ['date', 'metrics']
    return all(all(key in item for key in required_keys) for item in data)

@lru_cache(maxsize=128)
async def get_cached_instance_statistics() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(report_settings.INSTANCE_STATS_API_URL, timeout=10.0)
            response.raise_for_status()
            data = response.json()

        if not validate_instance_data(data):
            raise ValueError("Invalid instance statistics data format")

        return data
    except Exception as e:
        logger.error("Error fetching instance statistics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch instance statistics: {str(e)}")

@lru_cache(maxsize=128)
async def get_cached_prometheus_data(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    try:
        db: AsyncIOMotorDatabase = await MongoDBConnector.get_database()
        collection = db[mongo_settings.MONGO_SAVE_PROME_COLLECTION]

        data = await collection.find({"date": {"$gte": start_date, "$lte": end_date}}).sort("date", 1).to_list(None)

        if not validate_prometheus_data(data):
            raise ValueError("Invalid Prometheus data format")

        return data
    except Exception as e:
        logger.error("Error fetching Prometheus data", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch Prometheus data: {str(e)}")

async def invalidate_caches():
    get_cached_instance_statistics.cache_clear()
    get_cached_prometheus_data.cache_clear()