from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from modules.mongodb_connector import MongoDBConnector
from modules.time_utils import convert_utc_to_kst
from configs.mongo_conf import mongo_settings

router = APIRouter(tags=["Query Tool"])

logger = logging.getLogger(__name__)

class SlowQueryItem(BaseModel):
    instance: str
    pid: int
    user: str
    host: str
    db: str
    time: int
    sql_text: str
    start: datetime
    end: datetime

@router.get("/slow_queries", response_model=List[SlowQueryItem])
async def get_slow_queries(
    days: Optional[int] = Query(None, ge=1, le=30, description="Number of days to look back"),
    instance: Optional[List[str]] = Query(None, description="Filter by one or more instance names"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results to return"),
    skip: int = Query(0, ge=0, description="Number of results to skip")
):
    try:
        db = await MongoDBConnector.get_database()
        collection = db[mongo_settings.MONGO_SLOW_LOG_COLLECTION]

        query = {}

        if days is not None:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            query["start"] = {"$gte": start_date, "$lte": end_date}

        if instance:
            if len(instance) == 1:
                query["instance"] = instance[0]
            else:
                query["instance"] = {"$in": instance}

        sort = [("start", -1)]

        cursor = collection.find(query).sort(sort).skip(skip).limit(limit)

        items = []
        async for item in cursor:
            item['_id'] = str(item['_id'])
            item['start'] = convert_utc_to_kst(item['start'])
            item['end'] = convert_utc_to_kst(item['end']) if 'end' in item else None
            items.append(SlowQueryItem(**item))

        return items

    except Exception as e:
        logger.error(f"Error retrieving slow query items: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")