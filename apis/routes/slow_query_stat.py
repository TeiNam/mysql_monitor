from fastapi import APIRouter, Query
from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings
from datetime import datetime, timedelta
from typing import List, Dict
from modules.slack_utils import send_slack_notification
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


async def get_slow_query_stats(start_datetime, end_datetime):
    db = await MongoDBConnector.get_database()

    logger.info(f"Querying slow queries from {start_datetime} to {end_datetime}")

    # 전체 데이터 수 확인
    total_count = await db[mongo_settings.MONGO_SLOW_LOG_COLLECTION].count_documents({})
    logger.info(f"Total documents in collection: {total_count}")

    # 날짜 범위 내의 데이터 수 확인
    date_filter = {
        "start": {
            "$gte": start_datetime,
            "$lt": end_datetime
        }
    }
    filtered_count = await db[mongo_settings.MONGO_SLOW_LOG_COLLECTION].count_documents(date_filter)
    logger.info(f"Documents in date range: {filtered_count}")

    # 샘플 데이터 확인
    sample_data = await db[mongo_settings.MONGO_SLOW_LOG_COLLECTION].find_one()
    logger.info(f"Sample document: {sample_data}")

    aggregation_pipeline = [
        {"$match": date_filter},
        {
            "$group": {
                "_id": {
                    "instance": "$instance",
                    "db": "$db",
                    "user": "$user"
                },
                "total_count": {"$sum": 1},
                "max_time": {"$max": "$time"},
                "total_time": {"$sum": "$time"}
            }
        },
        {
            "$group": {
                "_id": "$_id.instance",
                "dbs": {
                    "$push": {
                        "db": "$_id.db",
                        "user": "$_id.user",
                        "count": "$total_count",
                        "max_time": "$max_time",
                        "total_time": "$total_time"
                    }
                }
            }
        },
        {
            "$unwind": "$dbs"
        },
        {
            "$project": {
                "_id": 0,
                "instance": "$_id",
                "db": "$dbs.db",
                "user": "$dbs.user",
                "count": "$dbs.count",
                "max_time": "$dbs.max_time",
                "total_time": "$dbs.total_time",
                "avg_time": {
                    "$round": [
                        {
                            "$cond": {"if": {"$ne": ["$dbs.count", 0]},
                                      "then": {"$divide": ["$dbs.total_time", "$dbs.count"]}, "else": 0}
                        },
                        3
                    ]
                }
            }
        }
    ]
    cursor = db[mongo_settings.MONGO_SLOW_LOG_COLLECTION].aggregate(aggregation_pipeline)
    result = await cursor.to_list(length=None)

    logger.info(f"Query result: {result}")

    return result

async def get_simplified_slow_query_stats(start_datetime, end_datetime):
    db = await MongoDBConnector.get_database()

    logger.info(f"Querying slow queries from {start_datetime} to {end_datetime}")

    date_filter = {
        "start": {
            "$gte": start_datetime,
            "$lt": end_datetime
        }
    }

    aggregation_pipeline = [
        {"$match": date_filter},
        {
            "$group": {
                "_id": None,
                "total_count": {"$sum": 1},
                "max_execution_time": {"$max": "$time"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "total_count": 1,
                "max_execution_time": 1
            }
        }
    ]

    cursor = db[mongo_settings.MONGO_SLOW_LOG_COLLECTION].aggregate(aggregation_pipeline)
    result = await cursor.to_list(length=None)

    logger.info(f"Query result: {result}")

    return result[0] if result else {"total_count": 0, "max_execution_time": 0}

async def send_slack_weekly_report(data: List[Dict], start_date: datetime.date, end_date: datetime.date):
    # 데이터 집계
    db_stats = {}
    total_count = 0
    max_execution_time = 0

    for item in data:
        db = item['db']
        count = item['count']
        max_time = item['max_time']

        # DB별 통계
        if db not in db_stats:
            db_stats[db] = {'count': 0, 'max_time': 0}
        db_stats[db]['count'] += count
        db_stats[db]['max_time'] = max(db_stats[db]['max_time'], max_time)

        # 전체 통계
        total_count += count
        max_execution_time = max(max_execution_time, max_time)

    # Slack 메시지 구성
    header = f"Weekly DB SlowQuery Report ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})"

    # DB 통계를 쿼리 수에 따라 내림차순 정렬
    sorted_db_stats = sorted(db_stats.items(), key=lambda x: x[1]['count'], reverse=True)

    db_summary = "\n".join([
        f"• *{db}*: {stats['count']} queries (Max: {stats['max_time']:.2f}s)"
        for db, stats in sorted_db_stats
    ])

    body = f"""
        *Summary:*
        • Total Slow Queries: {total_count:,}
        • Max Execution Time: {max_execution_time:.2f}s
        
        *DB Statistics:*
        {db_summary}
        """

    dashboard_url = "https://mgmt.grafana.devops.torder.tech/d/ZyF4Xc4Iz/orderservice-rds-slow-queries-mysql?from=now-12h&to=now&var-datasource=ddmd3ujwlqhhca&var-aws_account_id=488659748805&var-aws_region=ap-northeast-2&var-dbidentifier=All&orgId=1&refresh=1m"
    footer = f"<{dashboard_url}|자세한 정보는 대시보드에서 확인>"

    # Slack 알림 전송
    try:
        await send_slack_notification(header, body, footer)
    except ValueError as e:
        logger.error(f"Slack 알림 전송 실패: {e}")
        raise

    return True


@router.get("/slow_query_stats")
async def get_statistics(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format"),
    days: int = Query(7, description="Number of days to look back if no dates are provided")
):
    if not start_date and not end_date:
        end_datetime = datetime.now()
        start_datetime = end_datetime - timedelta(days=days)
    else:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) if end_date else None

    result = await get_slow_query_stats(start_datetime, end_datetime)

    return {
        "start_date": start_datetime.strftime("%Y-%m-%d") if start_datetime else None,
        "end_date": (end_datetime - timedelta(days=1)).strftime("%Y-%m-%d") if end_datetime else None,
        "is_cumulative": not (start_datetime and end_datetime),
        "data": result
    }

@router.get("/weekly_slow_query_stats")
async def get_weekly_statistics():
    today = datetime.now().date()
    days_since_monday = today.weekday()
    last_monday = today - timedelta(days=days_since_monday + 7)
    last_sunday = last_monday + timedelta(days=6)

    start_datetime = datetime.combine(last_monday, datetime.min.time())
    end_datetime = datetime.combine(last_sunday, datetime.max.time())

    logger.info(f"Fetching weekly stats from {start_datetime} to {end_datetime}")

    result = await get_slow_query_stats(start_datetime, end_datetime)

    if not result:
        logger.warning("No slow query data found for the specified week")

    try:
        await send_slack_weekly_report(result, last_monday, last_sunday)
    except Exception as e:
        logger.error(f"주간 보고서 전송 실패: {e}")

    return {
        "start_date": last_monday.strftime("%Y-%m-%d"),
        "end_date": last_sunday.strftime("%Y-%m-%d"),
        "is_cumulative": False,
        "data": result
    }