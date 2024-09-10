from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import timedelta
from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings

router = APIRouter()

kst_delta = timedelta(hours=9)


async def get_command_status(instance_name: str):
    db = await MongoDBConnector.get_database()
    collection = db[mongo_settings.MONGO_COM_STATUS_COLLECTION]
    document = await collection.find_one(
        {'instance_name': instance_name},
        {'_id': 0, 'timestamp': 1, 'command_status': 1},
        sort=[('timestamp', -1)]
    )
    return document


def transform_data_to_table_format(data: dict, command_names: Optional[List[str]] = None):
    transformed_data = []
    if data and "command_status" in data:
        timestamp = data.get("timestamp")
        if timestamp:
            timestamp = timestamp + kst_delta
            timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')

        for command, details in data["command_status"].items():
            if command_names and command not in command_names:
                continue
            row = {
                "timestamp": timestamp,
                "command": command,
                "total": details.get("total", 0),
                "avgForHours": details.get("avgForHours", 0),
                "avgForSeconds": details.get("avgForSeconds", 0),
                "percentage": details.get("percentage", 0)
            }
            transformed_data.append(row)
    return transformed_data


@router.get("/command_status")
async def read_status(
        instance_name: str = Query(..., description="The name of the instance to retrieve"),
        command: Optional[List[str]] = Query(None, description="List of command names to retrieve")
):
    data = await get_command_status(instance_name)
    if data:
        transformed_data = transform_data_to_table_format(data, command)
        return transformed_data
    raise HTTPException(status_code=404, detail="Data not found")