from fastapi import APIRouter, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
import httpx
import json
from typing import List, Dict, Any
import logging

from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings
from configs.prometheus_conf import PrometheusSettings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# 프로메테우스 설정 로드
prom_settings = PrometheusSettings()

async def get_prometheus_data(query: str, start: int, end: int) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            logger.debug(f"Sending request to Prometheus: query={query}, start={start}, end={end}")
            response = await client.get(
                f'{prom_settings.PROMETHEUS_URL}/api/v1/query_range',
                params={'query': query, 'start': start, 'end': end, 'step': '1h'}
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Received response from Prometheus: {data}")
            if data['status'] != 'success':
                raise ValueError(f"Prometheus API returned non-success status: {data['status']}")
            return data['data']['result']
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise HTTPException(status_code=e.response.status_code,
                                detail=f"Prometheus API request failed: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise HTTPException(status_code=500,
                                detail=f"Failed to parse Prometheus API response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(status_code=500,
                                detail=f"Error fetching data from Prometheus: {str(e)}")

def calculate_statistics(values: List[List[float]]) -> Dict[str, Any]:
    if not values:
        logger.warning("No values provided to calculate_statistics")
        return {'max': {'value': 0, 'timestamp': None}, 'min': {'value': 0, 'timestamp': None}, 'avg': 0}

    max_value = max(values, key=lambda x: x[1])
    min_value = min(values, key=lambda x: x[1])
    avg_value = sum(float(v[1]) for v in values) / len(values)

    return {
        'max': {'value': float(max_value[1]), 'timestamp': datetime.fromtimestamp(max_value[0]).isoformat()},
        'min': {'value': float(min_value[1]), 'timestamp': datetime.fromtimestamp(min_value[0]).isoformat()},
        'avg': avg_value
    }

async def process_metric(metric: str, start_unix: int, end_unix: int) -> Dict[str, Dict[str, Any]]:
    query = f'{metric}{{dbidentifier=~"{"|".join(prom_settings.DB_IDENTIFIERS)}"}}'
    data = await get_prometheus_data(query, start_unix, end_unix)
    logger.debug(f"Received data for metric {metric}: {data}")

    if not data:
        logger.warning(f"No data received for metric: {metric}")
        return {}

    result = {}
    for item in data:
        instance = item['metric']['dbidentifier']
        values = [(float(v[0]), float(v[1])) for v in item['values']]
        result[instance] = calculate_statistics(values)

    return result

@router.get("/collect-daily-metrics")
async def collect_daily_metrics(date: str = Query(None, description="Date in YYYY-MM-DD format")):
    try:
        db: AsyncIOMotorDatabase = await MongoDBConnector.get_database()
        collection = db[mongo_settings.MONGO_SAVE_PROME_COLLECTION]

        if date:
            start_time = datetime.strptime(date, "%Y-%m-%d")
            end_time = start_time + timedelta(days=1)
        else:
            end_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = end_time - timedelta(days=1)

        logger.info(f"Collecting metrics for date range: {start_time} to {end_time}")

        end_unix = int(end_time.timestamp())
        start_unix = int(start_time.timestamp())

        existing_data = await collection.find_one({"date": start_time.date().isoformat()})
        if existing_data:
            logger.info(f"Data already exists for {start_time.date().isoformat()}")
            return {"message": f"{start_time.date().isoformat()} 날짜의 데이터가 이미 존재합니다.", "data": existing_data["metrics"]}

        all_metrics = {}
        for metric in prom_settings.METRICS:
            metric_data = await process_metric(metric, start_unix, end_unix)
            for instance, data in metric_data.items():
                if instance not in all_metrics:
                    all_metrics[instance] = {}
                all_metrics[instance][metric] = data

        if not all_metrics:
            logger.warning("No metrics collected")
            raise HTTPException(status_code=404, detail="No data found for the specified date range")

        document = {
            "date": start_time.date().isoformat(),
            "metrics": all_metrics,
            "created_at": datetime.utcnow()
        }

        await collection.insert_one(document)
        logger.info(f"Metrics for {start_time.date().isoformat()} successfully added to MongoDB")

        return {"message": f"{start_time.date().isoformat()} 일자의 프로메테우스 메트릭이 성공적으로 MongoDB에 추가되었습니다.", "data": all_metrics}

    except HTTPException as he:
        logger.error(f"HTTP exception occurred: {he}")
        raise he
    except ValueError as ve:
        logger.error(f"Value error occurred: {ve}")
        raise HTTPException(status_code=400, detail=f"잘못된 날짜 형식입니다: {str(ve)}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 처리 중 오류 발생: {str(e)}")