from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import timedelta, datetime
from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings
import pytz

router = APIRouter()

kst = pytz.timezone('Asia/Seoul')

async def get_disk_usage_status(instance_name: str, metric_names: Optional[List[str]] = None,
                                days: Optional[int] = None):
    db: AsyncIOMotorDatabase = await MongoDBConnector.get_database()
    collection = db[mongo_settings.MONGO_DISK_USAGE_COLLECTION]
    query = {'instance_name': instance_name}

    if days is not None:
        end_date = datetime.now(kst)
        start_date = end_date - timedelta(days=days)
        query['timestamp'] = {'$gte': start_date, '$lte': end_date}

    projection = {'_id': 0, 'timestamp': 1}

    # metric_names가 제공된 경우, 해당 메트릭만 포함하도록 projection 수정
    if metric_names:
        for metric in metric_names:
            projection[f'disk_status.{metric}'] = 1
    else:
        projection['disk_status'] = 1

    cursor = collection.find(query, projection).sort('timestamp', 1)  # 1은 오름차순, -1은 내림차순

    results = await cursor.to_list(length=None)

    # Convert UTC timestamp to KST
    for result in results:
        if 'timestamp' in result:
            result['timestamp'] = result['timestamp'].replace(tzinfo=pytz.UTC).astimezone(kst)

    # metric_names가 제공된 경우, 결과를 재구성
    if metric_names:
        for result in results:
            filtered_disk_status = {}
            for metric in metric_names:
                if 'disk_status' in result and metric in result['disk_status']:
                    filtered_disk_status[metric] = result['disk_status'][metric]
            result['disk_status'] = filtered_disk_status

    return results

def transform_data_to_table_format(data_list: List[dict], metric_names: Optional[List[str]] = None):
    transformed_data = []
    for data in data_list:
        timestamp = data.get("timestamp")
        if timestamp:
            if not timestamp.tzinfo:
                timestamp = kst.localize(timestamp)
            timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')

        if "disk_status" in data:
            for metric, details in data["disk_status"].items():
                if metric_names and metric not in metric_names:
                    continue
                row = {
                    "timestamp": timestamp,
                    "name": metric,
                    "total": details.get("total", 0),
                    "avgForHours": details.get("avgForHours", 0),
                    "avgForSeconds": details.get("avgForSeconds", 0)
                }
                transformed_data.append(row)
    return transformed_data

@router.get("/disk_usage")
async def read_status(
        instance_name: str = Query(..., description="The name of the instance to retrieve"),
        metric_name: Optional[List[str]] = Query(None, description="List of metric names to retrieve", alias="metric"),
        days: Optional[int] = Query(None, description="Number of days to retrieve data for")
):
    data_list = await get_disk_usage_status(instance_name, metric_name, days)
    if data_list:
        transformed_data = transform_data_to_table_format(data_list, metric_name)
        return transformed_data
    raise HTTPException(status_code=404, detail="Data not found")