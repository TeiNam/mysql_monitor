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


@router.get("/instance-statistics-by-period")
async def get_instance_statistics_by_period(start_date: str, end_date: str):
    try:
        try:
            query_start = datetime.strptime(start_date, "%Y-%m-%d")
            query_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요.")

        if query_start >= query_end:
            raise HTTPException(status_code=400, detail="시작일이 종료일보다 늦을 수 없습니다.")

        db = await get_database()
        collection = db[mongo_settings.MONGO_RDS_INSTANCE_ALL_STAT_COLLECTION]

        # 1. 해당 기간의 데이터가 있는 첫 날짜와 마지막 날짜 찾기
        date_range_pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": query_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "$lt": query_end.strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "first_date": {"$min": "$timestamp"},
                    "last_date": {"$max": "$timestamp"}
                }
            }
        ]

        date_range = await collection.aggregate(date_range_pipeline).to_list(None)
        if not date_range:
            return {
                "year": query_start.year,
                "month": query_start.month,
                "total_instances_start": 0,
                "total_instances_end": 0,
                "instances_added": 0,
                "instances_removed": 0,
                "added_instances": [],
                "removed_instances": [],
                "data_range": {
                    "start": None,
                    "end": None
                }
            }

        # timestamp에서 날짜 부분만 추출
        first_date = date_range[0]["first_date"].split()[0]
        last_date = date_range[0]["last_date"].split()[0]

        logger.info(f"Data available from {first_date} to {last_date}")

        # 2. 첫 날짜의 계정별 인스턴스 집계
        first_day_pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$regex": f"^{first_date}"  # 날짜로 시작하는 데이터 매칭
                    }
                }
            },
            {
                "$unwind": "$instances"
            },
            {
                "$group": {
                    "_id": None,
                    "instance_ids": {"$addToSet": "$instances.DBInstanceIdentifier"}
                }
            }
        ]

        # 3. 마지막 날짜의 계정별 인스턴스 집계
        last_day_pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$regex": f"^{last_date}"  # 날짜로 시작하는 데이터 매칭
                    }
                }
            },
            {
                "$unwind": "$instances"
            },
            {
                "$group": {
                    "_id": None,
                    "instance_ids": {"$addToSet": "$instances.DBInstanceIdentifier"}
                }
            }
        ]

        first_day_result = await collection.aggregate(first_day_pipeline).to_list(None)
        last_day_result = await collection.aggregate(last_day_pipeline).to_list(None)

        if not first_day_result or not last_day_result:
            raise HTTPException(status_code=500, detail="데이터 집계 중 오류가 발생했습니다.")

        first_day_instances = set(first_day_result[0]["instance_ids"])
        last_day_instances = set(last_day_result[0]["instance_ids"])

        # 4. 변경사항 계산
        added_instances = list(last_day_instances - first_day_instances)
        removed_instances = list(first_day_instances - last_day_instances)

        logger.info(f"First day ({first_date}) instances count: {len(first_day_instances)}")
        logger.info(f"Last day ({last_date}) instances count: {len(last_day_instances)}")
        logger.info(f"Added instances: {len(added_instances)}")
        logger.info(f"Removed instances: {len(removed_instances)}")

        return {
            "year": query_start.year,
            "month": query_start.month,
            "total_instances_start": len(first_day_instances),
            "total_instances_end": len(last_day_instances),
            "instances_added": len(added_instances),
            "instances_removed": len(removed_instances),
            "added_instances": sorted(added_instances),
            "removed_instances": sorted(removed_instances),
            "data_range": {
                "start": first_date,
                "end": last_date
            }
        }

    except Exception as e:
        logger.error(f"Error in get_instance_statistics_by_period: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"기간별 통계 생성 중 오류 발생: {str(e)}")