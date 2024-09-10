from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import timedelta, datetime
from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings

router = APIRouter()

kst_delta = timedelta(hours=9)

async def get_disk_usage_status(instance_name: str, metric_names: Optional[List[str]] = None):
    db = await MongoDBConnector.get_database()
    collection = db[mongo_settings.MONGO_DISK_USAGE_COLLECTION]
    query = {'instance_name': instance_name}

    projection = {'_id': 0, 'timestamp': 1, 'command_status': 1, 'metrics': 1}
    document = await collection.find_one(query, projection, sort=[('timestamp', -1)])
    return document if document else None

def transform_data_to_table_format(data: dict, metric_names: Optional[List[str]] = None):
    transformed_data = []
    if data:
        timestamp = data.get("timestamp")
        if timestamp:
            timestamp = timestamp + kst_delta
            timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')

        if "command_status" in data:
            for metric, details in data["command_status"].items():
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
        elif "metrics" in data:
            for metric in data["metrics"]:
                if metric_names and metric["name"] not in metric_names:
                    continue
                row = {
                    "timestamp": timestamp,
                    "name": metric["name"],
                    "total": metric.get("value", 0),
                    "avgForHours": metric.get("avg_for_hours", 0),
                    "avgForSeconds": metric.get("avg_for_seconds", 0)
                }
                transformed_data.append(row)
    return transformed_data

@router.get("/disk_usage")
async def read_status(
        instance_name: str = Query(..., description="The name of the instance to retrieve"),
        metric_name: Optional[List[str]] = Query(None, description="List of metric names to retrieve", alias="metric")
):
    data = await get_disk_usage_status(instance_name)
    if data:
        transformed_data = transform_data_to_table_format(data, metric_name)
        return transformed_data
    raise HTTPException(status_code=404, detail="Data not found")