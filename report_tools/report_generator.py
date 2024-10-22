import os
import asyncio
import aiofiles
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Dict, Any, List
import structlog
from configs.report_conf import report_settings
from configs.openai_conf import openai_settings
from openai import AsyncOpenAI
from functools import lru_cache
from .data_retrieval import get_cached_instance_statistics, get_cached_prometheus_data
from .graph_generation import create_instance_graphs, create_prometheus_graphs

logger = structlog.get_logger()
router = APIRouter()
client = AsyncOpenAI(api_key=openai_settings.OPENAI_API_KEY)

def validate_date_format(date_string: str) -> bool:
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False

@lru_cache(maxsize=128)
def get_cached_instance_statistics_wrapper():
    return get_cached_instance_statistics()

@lru_cache(maxsize=128)
def get_cached_prometheus_data_wrapper(start_date: str, end_date: str):
    return get_cached_prometheus_data(start_date, end_date)

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
    2. 해당기간동안 새로 생성된 인스턴스와 제거된 인스턴스
    3. 각 인스턴스의 성능 지표 요약
    4. orderservice 라는 이름을 가진 인스턴스들의 성능지표 요약
    5. 최대 성능 치가 인스턴스 성능의 30%가 되지 않는 인스턴스
    6. AWS 비용 단가에 따른 해당 월의 인스턴스 예상 사용 비용

    각 항목에 대해 관찰된 사실 만을 간결하게 서술한 후에 차후 대응 할만한 의견을 제시.
    """

    try:
        response = await client.chat.completions.create(
            model=openai_settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "당신은 AWS RDS 인스턴스 통계 및 성능 데이터를 객관적으로 요약하는 분석가입니다. 오직 관찰된 사실만을 보고하고, 의견이나 제안은 제시하지 않습니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=openai_settings.OPENAI_MAX_TOKENS,
            temperature=openai_settings.OPENAI_TEMPERATURE
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ChatGPT 분석 생성 중 오류 발생: {str(e)}"

async def create_integrated_report(instance_data: Dict[str, Any], prometheus_data: List[Dict[str, Any]],
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

        # 수정된 부분: 래퍼 함수를 사용하여 코루틴을 얻습니다
        instance_data_coro = get_cached_instance_statistics_wrapper()
        prometheus_data_coro = get_cached_prometheus_data_wrapper(start_date, end_date)

        # gather를 사용하여 코루틴을 실행합니다
        instance_data, prometheus_data = await asyncio.gather(
            instance_data_coro, prometheus_data_coro
        )

        if not prometheus_data:
            raise HTTPException(status_code=404, detail="No data found for the specified date range")

        report_date = datetime.strptime(end_date, "%Y-%m-%d")
        report_dir = report_settings.get_report_dir(report_date)
        os.makedirs(report_dir, exist_ok=True)

        # 병렬로 그래프 생성 및 분석 수행
        (account_graph, region_graph, class_graph), (cpu_graph, iops_graph), analysis = await asyncio.gather(
            create_instance_graphs(instance_data, end_date, report_dir),
            create_prometheus_graphs(prometheus_data, start_date, end_date, report_dir),
            get_chatgpt_analysis(instance_data, prometheus_data)
        )

        report = await create_integrated_report(
            instance_data, prometheus_data,
            end_date, start_date, end_date,
            account_graph, region_graph, class_graph,
            cpu_graph, iops_graph, analysis
        )

        filename = f"integrated_rds_report_{start_date}_{end_date}.md"
        file_path = os.path.join(report_dir, filename)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(report)

        logger.info("Report generated successfully", file_path=file_path)
        return {"message": "Integrated RDS report generated successfully", "file_path": file_path}

    except HTTPException as he:
        logger.error("HTTP exception occurred", status_code=he.status_code, detail=he.detail)
        raise
    except Exception as e:
        logger.exception("Unexpected error during report generation", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

# 캐시 무효화 함수
async def invalidate_caches():
    get_cached_instance_statistics_wrapper.cache_clear()
    get_cached_prometheus_data_wrapper.cache_clear()