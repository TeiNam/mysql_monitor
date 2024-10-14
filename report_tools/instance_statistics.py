from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_database() -> AsyncIOMotorDatabase:
    return await MongoDBConnector.get_database()

async def aggregate_data(collection, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return await collection.aggregate(pipeline).to_list(length=None)

@router.get("/daily-instance-statistics")
async def get_daily_instance_statistics():
    try:
        db = await get_database()
        collection = db[mongo_settings.MONGO_RDS_INSTANCE_ALL_STAT_COLLECTION]

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        pipeline = [
            {"$match": {"timestamp": {"$gte": today.strftime("%Y-%m-%d %H:%M:%S"), "$lt": tomorrow.strftime("%Y-%m-%d %H:%M:%S")}}},
            {"$unwind": "$instances"},
            {"$group": {
                "_id": None,
                "total_instances": {"$sum": 1},
                "accounts": {"$addToSet": "$account_id"},
                "dev_instances": {"$sum": {"$cond": [{"$eq": ["$instances.Tags.env", "dev"]}, 1, 0]}},
                "prd_instances": {"$sum": {"$cond": [{"$eq": ["$instances.Tags.env", "prd"]}, 1, 0]}},
                "regions": {"$addToSet": "$instances.Region"},
                "instance_classes": {"$push": "$instances.DBInstanceClass"}
            }},
            {"$project": {
                "_id": 0,
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": today}},
                "total_instances": 1,
                "account_count": {"$size": "$accounts"},
                "dev_instances": 1,
                "prd_instances": 1,
                "region_count": {"$size": "$regions"},
                "instance_classes": 1
            }}
        ]

        result = await aggregate_data(collection, pipeline)

        if not result:
            return {
                "date": today.date().isoformat(),
                "total_instances": 0,
                "account_count": 0,
                "dev_instances": 0,
                "prd_instances": 0,
                "region_count": 0,
                "instance_classes": {}
            }

        result = result[0]
        result["instance_classes"] = {cls: result["instance_classes"].count(cls) for cls in set(result["instance_classes"])}

        account_pipeline = [
            {"$match": {"timestamp": {"$gte": today.strftime("%Y-%m-%d %H:%M:%S"), "$lt": tomorrow.strftime("%Y-%m-%d %H:%M:%S")}}},
            {"$group": {"_id": "$account_id", "instance_count": {"$sum": "$total_instances"}}},
            {"$project": {"_id": 0, "account_id": "$_id", "instance_count": 1}}
        ]

        region_pipeline = [
            {"$match": {"timestamp": {"$gte": today.strftime("%Y-%m-%d %H:%M:%S"), "$lt": tomorrow.strftime("%Y-%m-%d %H:%M:%S")}}},
            {"$unwind": "$instances"},
            {"$group": {"_id": "$instances.Region", "instance_count": {"$sum": 1}}},
            {"$project": {"_id": 0, "region": "$_id", "instance_count": 1}}
        ]

        result["accounts"] = await aggregate_data(collection, account_pipeline)
        result["regions"] = await aggregate_data(collection, region_pipeline)

        return result

    except Exception as e:
        logger.error(f"Error in get_daily_instance_statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"데이터베이스 쿼리 중 오류 발생: {str(e)}")

@router.get("/monthly-instance-statistics")
async def get_monthly_instance_statistics(year: int, month: int):
    try:
        db = await get_database()
        collection = db[mongo_settings.MONGO_RDS_INSTANCE_ALL_STAT_COLLECTION]

        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        async def get_instance_state(date: datetime) -> Dict[str, Dict]:
            pipeline = [
                {"$match": {"timestamp": {"$gte": date.strftime("%Y-%m-%d 00:00:00"), "$lt": (date + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")}}},
                {"$unwind": "$instances"},
                {"$group": {"_id": "$instances.DBInstanceIdentifier", "instance": {"$first": "$instances"}}}
            ]
            result = await aggregate_data(collection, pipeline)
            return {doc["_id"]: doc["instance"] for doc in result}

        start_state = await get_instance_state(start_date)
        end_state = await get_instance_state(end_date - timedelta(days=1))

        added_instances = [instance for instance_id, instance in end_state.items() if instance_id not in start_state]
        removed_instances = [instance for instance_id, instance in start_state.items() if instance_id not in end_state]

        return {
            "year": year,
            "month": month,
            "total_instances_start": len(start_state),
            "total_instances_end": len(end_state),
            "instances_added": len(added_instances),
            "instances_removed": len(removed_instances),
            "added_instances": added_instances,
            "removed_instances": removed_instances
        }

    except Exception as e:
        logger.error(f"Error in get_monthly_instance_statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"월간 통계 생성 중 오류 발생: {str(e)}")