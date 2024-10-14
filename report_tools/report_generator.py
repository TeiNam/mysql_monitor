from fastapi import APIRouter, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
from typing import Dict, Any, List
import httpx
from modules.mongodb_connector import MongoDBConnector
from configs.mongo_conf import mongo_settings
from configs.openai_conf import openai_settings
from configs.report_conf import report_settings
from openai import AsyncOpenAI

import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

client = AsyncOpenAI(api_key=openai_settings.OPENAI_API_KEY)

def validate_date_format(date_string: str) -> bool:
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def validate_instance_data(data: Dict[str, Any]) -> bool:
    required_keys = ['total_instances', 'dev_instances', 'prd_instances', 'account_count', 'region_count', 'accounts', 'regions', 'instance_classes']
    return all(key in data for key in required_keys)

def validate_prometheus_data(data: List[Dict[str, Any]]) -> bool:
    if not data:
        return False
    required_keys = ['date', 'metrics']
    return all(all(key in item for key in required_keys) for item in data)


async def get_instance_statistics() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(report_settings.INSTANCE_STATS_API_URL, timeout=10.0)
            response.raise_for_status()
            data = response.json()

        if not validate_instance_data(data):
            raise ValueError("Invalid instance statistics data format")

        return data
    except Exception as e:
        logger.error(f"Error fetching instance statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch instance statistics: {str(e)}")

async def get_prometheus_data(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    try:
        db: AsyncIOMotorDatabase = await MongoDBConnector.get_database()
        collection = db[mongo_settings.MONGO_SAVE_PROME_COLLECTION]

        data = await collection.find({"date": {"$gte": start_date, "$lte": end_date}}).sort("date", 1).to_list(None)

        if not validate_prometheus_data(data):
            raise ValueError("Invalid Prometheus data format")

        return data
    except Exception as e:
        logger.error(f"Error fetching Prometheus data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch Prometheus data: {str(e)}")

def create_instance_graphs(data: Dict[str, Any], date: str, report_dir: str):
    # 계정별 그래프
    plt.figure(figsize=(10, 6))
    accounts = [account['account_id'] for account in data['accounts']]
    instance_counts = [account['instance_count'] for account in data['accounts']]
    plt.bar(accounts, instance_counts)
    plt.title("Instances by Account")
    plt.xlabel("Account ID")
    plt.ylabel("Instance Count")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    account_graph_path = os.path.join(report_dir, f"account_graph_{date}.png")
    plt.savefig(account_graph_path)
    plt.close()

    # 리전별 그래프
    plt.figure(figsize=(8, 6))
    regions = [region['region'] for region in data['regions']]
    region_counts = [region['instance_count'] for region in data['regions']]
    plt.pie(region_counts, labels=regions, autopct='%1.1f%%', startangle=90)
    plt.title("Instances by Region")
    plt.axis('equal')
    region_graph_path = os.path.join(report_dir, f"region_graph_{date}.png")
    plt.savefig(region_graph_path)
    plt.close()

    # 인스턴스 클래스별 그래프
    plt.figure(figsize=(12, 6))
    classes = list(data['instance_classes'].keys())
    class_counts = list(data['instance_classes'].values())
    plt.bar(classes, class_counts)
    plt.title("Instance Class Distribution")
    plt.xlabel("Instance Class")
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    class_graph_path = os.path.join(report_dir, f"class_graph_{date}.png")
    plt.savefig(class_graph_path)
    plt.close()

    return account_graph_path, region_graph_path, class_graph_path

def create_prometheus_graphs(data: List[Dict[str, Any]], start_date: str, end_date: str, report_dir: str):
    # CPU 사용률 그래프
    plt.figure(figsize=(12, 6))
    for instance in data[0]['metrics']:
        dates = [d['date'] for d in data]
        cpu_usage = [d['metrics'][instance]['rds_cpu_usage_percent_average']['avg'] for d in data]
        plt.plot(dates, cpu_usage, label=instance)
    plt.title("Average CPU Usage by Instance")
    plt.xlabel("Date")
    plt.ylabel("CPU Usage (%)")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    cpu_graph_path = os.path.join(report_dir, f"cpu_usage_{start_date}_{end_date}.png")
    plt.savefig(cpu_graph_path)
    plt.close()


    # IOPS 그래프
    plt.figure(figsize=(12, 6))
    for instance in data[0]['metrics']:
        dates = [d['date'] for d in data]
        read_iops = [d['metrics'][instance]['rds_read_iops_average']['avg'] for d in data]
        write_iops = [d['metrics'][instance]['rds_write_iops_average']['avg'] for d in data]
        plt.plot(dates, read_iops, label=f"{instance} Read")
        plt.plot(dates, write_iops, label=f"{instance} Write")
    plt.title("Average Read and Write IOPS by Instance")
    plt.xlabel("Date")
    plt.ylabel("IOPS")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    iops_graph_path = os.path.join(report_dir, f"iops_{start_date}_{end_date}.png")
    plt.savefig(iops_graph_path)
    plt.close()

    return cpu_graph_path, iops_graph_path

async def get_chatgpt_analysis(instance_data: Dict[str, Any], prometheus_data: List[Dict[str, Any]]) -> str:
    instance_summary = f"""
    총 인스턴스 수: {instance_data['total_instances']}
    개발 인스턴스 수: {instance_data['dev_instances']}
    운영 인스턴스 수: {instance_data['prd_instances']}
    계정 수: {instance_data['account_count']}
    리전 수: {instance_data['region_count']}

    계정별 인스턴스 분포: {instance_data['accounts']}
    리전별 인스턴스 분포: {instance_data['regions']}
    인스턴스 클래스별 분포: {instance_data['instance_classes']}
    """

    prometheus_summary = f"""
    분석 기간: {prometheus_data[0]['date']} ~ {prometheus_data[-1]['date']}

    인스턴스별 평균 지표:
    """

    for instance in prometheus_data[0]['metrics']:
        avg_cpu = sum(d['metrics'][instance]['rds_cpu_usage_percent_average']['avg'] for d in prometheus_data) / len(prometheus_data)
        avg_read_iops = sum(d['metrics'][instance]['rds_read_iops_average']['avg'] for d in prometheus_data) / len(prometheus_data)
        avg_write_iops = sum(d['metrics'][instance]['rds_write_iops_average']['avg'] for d in prometheus_data) / len(prometheus_data)

        prometheus_summary += f"""
        {instance}:
        - 평균 CPU 사용률: {avg_cpu:.2f}%
        - 평균 Read IOPS: {avg_read_iops:.2f}
        - 평균 Write IOPS: {avg_write_iops:.2f}
        """

    prompt = f"""
    다음은 AWS RDS 인스턴스 통계 및 성능 메트릭 데이터입니다:

    1. 인스턴스 통계:
    {instance_summary}

    2. 성능 메트릭:
    {prometheus_summary}

    이 데이터를 바탕으로 다음 사항들에 대한 객관적인 사실만을 한글로 나열해주세요. 의견이나 제안은 포함하지 마세요:

    1. RDS 인스턴스 사용 현황 및 분포 요약
    2. 각 인스턴스의 성능 지표 요약
    3. 인스턴스 간 성능 비교 결과
    4. 최고 및 최저 성능을 보이는 인스턴스와 그 수치
    5. 전체 기간 동안의 성능 변화 추세

    각 항목에 대해 관찰된 사실만을 간결하게 서술해주세요.
    """

    try:
        response = await client.chat.completions.create(
            model=openai_settings.OPENAI_MODEL,
            messages=[
                {"role": "system",
                 "content": "당신은 AWS RDS 인스턴스 통계 및 성능 데이터를 객관적으로 요약하는 분석가입니다. 오직 관찰된 사실만을 보고하고, 의견이나 제안은 제시하지 않습니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=openai_settings.OPENAI_MAX_TOKENS,
            temperature=openai_settings.OPENAI_TEMPERATURE
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ChatGPT 분석 생성 중 오류 발생: {str(e)}"

def create_integrated_report(instance_data: Dict[str, Any], prometheus_data: List[Dict[str, Any]],
                             date: str, start_date: str, end_date: str,
                             account_graph: str, region_graph: str, class_graph: str,
                             cpu_graph: str, iops_graph: str, analysis: str) -> str:
    report = f"# 통합 RDS 인스턴스 및 성능 분석 리포트 ({start_date} ~ {end_date})\n\n"

    # 1. 인스턴스 통계 요약
    report += "## 1. RDS 인스턴스 통계 요약\n\n"
    report += f"- 총 인스턴스 수: {instance_data['total_instances']}\n"
    report += f"- 개발 인스턴스 수: {instance_data['dev_instances']}\n"
    report += f"- 운영 인스턴스 수: {instance_data['prd_instances']}\n"
    report += f"- 총 계정 수: {instance_data['account_count']}\n"
    report += f"- 총 리전 수: {instance_data['region_count']}\n\n"

    # 2. 인스턴스 분포
    report += "## 2. 인스턴스 분포\n\n"
    report += "### 2.1 계정별 인스턴스 분포\n\n"
    report += "| Account ID | Instance Count |\n"
    report += "|------------|----------------|\n"
    for account in instance_data['accounts']:
        report += f"| {account['account_id']} | {account['instance_count']} |\n"
    report += f"\n![Instances by Account]({os.path.basename(account_graph)})\n\n"

    report += "### 2.2 리전별 인스턴스 분포\n\n"
    report += "| Region | Instance Count |\n"
    report += "|--------|----------------|\n"
    for region in instance_data['regions']:
        report += f"| {region['region']} | {region['instance_count']} |\n"
    report += f"\n![Instances by Region]({os.path.basename(region_graph)})\n\n"

    report += "### 2.3 인스턴스 클래스 분포\n\n"
    report += "| Instance Class | Count |\n"
    report += "|----------------|-------|\n"
    for instance_class, count in instance_data['instance_classes'].items():
        report += f"| {instance_class} | {count} |\n"
    report += f"\n![Instance Class Distribution]({os.path.basename(class_graph)})\n\n"

    # 3. 성능 메트릭 분석
    report += "## 3. 성능 메트릭 분석\n\n"
    report += f"분석 기간: {start_date} ~ {end_date}\n"
    report += f"총 데이터 포인트: {len(prometheus_data)}개\n\n"

    report += "### 3.1 인스턴스별 평균 성능 지표\n\n"
    for instance in prometheus_data[0]['metrics']:
        report += f"#### {instance}\n\n"
        avg_cpu = sum(d['metrics'][instance]['rds_cpu_usage_percent_average']['avg'] for d in prometheus_data) / len(prometheus_data)
        avg_read_iops = sum(d['metrics'][instance]['rds_read_iops_average']['avg'] for d in prometheus_data) / len(prometheus_data)
        avg_write_iops = sum(d['metrics'][instance]['rds_write_iops_average']['avg'] for d in prometheus_data) / len(prometheus_data)
        avg_connections = sum(d['metrics'][instance]['rds_database_connections_average']['avg'] for d in prometheus_data) / len(prometheus_data)

        report += f"- 평균 CPU 사용률: {avg_cpu:.2f}%\n"
        report += f"- 평균 Read IOPS: {avg_read_iops:.2f}\n"
        report += f"- 평균 Write IOPS: {avg_write_iops:.2f}\n"
        report += f"- 평균 데이터베이스 연결 수: {avg_connections:.2f}\n\n"

    report += "### 3.2 성능 그래프\n\n"
    report += f"#### CPU 사용률\n\n![CPU Usage Graph]({os.path.basename(cpu_graph)})\n\n"
    report += f"#### IOPS\n\n![IOPS Graph]({os.path.basename(iops_graph)})\n\n"

    # 4. ChatGPT 분석
    report += "## 4. 종합 분석 및 인사이트\n\n"
    report += analysis + "\n\n"

    return report


@router.get("/generate-integrated-report")
async def generate_integrated_report(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format")
):
    try:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).date().isoformat()
        if end_date is None:
            end_date = datetime.now().date().isoformat()

        if not validate_date_format(start_date) or not validate_date_format(end_date):
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

        instance_data = await get_instance_statistics()
        prometheus_data = await get_prometheus_data(start_date, end_date)

        if not prometheus_data:
            raise HTTPException(status_code=404, detail="No data found for the specified date range")

        report_date = datetime.strptime(end_date, "%Y-%m-%d")
        report_dir = report_settings.get_report_dir(report_date)
        os.makedirs(report_dir, exist_ok=True)

        account_graph, region_graph, class_graph = create_instance_graphs(instance_data, end_date, report_dir)
        cpu_graph, iops_graph = create_prometheus_graphs(prometheus_data, start_date, end_date, report_dir)

        analysis = await get_chatgpt_analysis(instance_data, prometheus_data)

        report = create_integrated_report(
            instance_data, prometheus_data,
            end_date, start_date, end_date,
            account_graph, region_graph, class_graph,
            cpu_graph, iops_graph, analysis
        )

        filename = f"integrated_rds_report_{start_date}_{end_date}.md"
        file_path = os.path.join(report_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"Report generated successfully: {file_path}")
        return {"message": "Integrated RDS report generated successfully", "file_path": file_path}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")