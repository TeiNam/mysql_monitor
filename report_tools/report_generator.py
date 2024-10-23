import os
import asyncio
import aiofiles
import httpx
import zipfile
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
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


async def get_monthly_instance_changes(start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
    """월간 인스턴스 변화 정보를 가져오는 함수"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Fetching monthly instance changes for period: {start_date} to {end_date}")
            response = await client.get(
                "http://localhost:8000/api/v1/reports/instance-statistics-by-period",
                params={
                    "start_date": start_date,
                    "end_date": end_date
                }
            )

            if response.status_code == 404:
                logger.warning("No monthly instance changes data found")
                return None

            response.raise_for_status()
            data = response.json()
            logger.info("Successfully fetched monthly instance changes",
                        start_count=data.get('total_instances_start'),
                        end_count=data.get('total_instances_end'))
            return data

    except httpx.TimeoutException:
        logger.error("Timeout while fetching monthly instance changes")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error while fetching monthly instance changes: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while fetching monthly instance changes: {str(e)}")
        return None


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
    2. RDS 인스턴스 변화
    3. 각 인스턴스의 성능 지표 요약
    4. 최대 성능 치가 인스턴스 성능의 30%가 되지 않는 인스턴스
    5. 

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
                                   cpu_graph: str, iops_graph: str, analysis: str,
                                   monthly_changes: Dict[str, Any]) -> str:
    report = f"# 통합 RDS 인스턴스 및 성능 분석 리포트 ({start_date} ~ {end_date})\n\n"

    # 1. 현재 인스턴스 통계
    report += "## 1. RDS 인스턴스 통계 요약\n\n"
    report += f"- 총 인스턴스 수: {instance_data['total_instances']}\n"
    report += f"- 개발 인스턴스 수: {instance_data['dev_instances']}\n"
    report += f"- 운영 인스턴스 수: {instance_data['prd_instances']}\n"
    report += f"- 총 계정 수: {instance_data['account_count']}\n"
    report += f"- 총 리전 수: {instance_data['region_count']}\n\n"

    # 2. 월간 변화 정보
    if monthly_changes:
        report += "## 2. 월간 인스턴스 변화\n\n"
        report += f"### 분석 기간: {monthly_changes['data_range']['start']} ~ {monthly_changes['data_range']['end']}\n\n"
        report += "#### 인스턴스 수 변화\n"
        report += f"- 시작 시점 인스턴스 수: {monthly_changes['total_instances_start']}\n"
        report += f"- 종료 시점 인스턴스 수: {monthly_changes['total_instances_end']}\n"
        report += f"- 순증감: {monthly_changes['total_instances_end'] - monthly_changes['total_instances_start']}\n\n"

        if monthly_changes['added_instances']:
            report += "#### 신규 생성된 인스턴스\n"
            for instance in sorted(monthly_changes['added_instances']):
                report += f"- {instance}\n"
            report += "\n"

        if monthly_changes['removed_instances']:
            report += "#### 삭제된 인스턴스\n"
            for instance in sorted(monthly_changes['removed_instances']):
                report += f"- {instance}\n"
            report += "\n"

        report += f"총 {monthly_changes['instances_added']}개의 인스턴스가 생성되었고, "
        report += f"{monthly_changes['instances_removed']}개의 인스턴스가 삭제되었습니다.\n\n"
        report += "---\n\n"

    # 3. 인스턴스 분포
    report += "## 3. 인스턴스 분포\n\n"
    report += "### 3.1 계정별 인스턴스 분포\n\n"
    report += "| Account ID | Instance Count |\n"
    report += "|------------|----------------|\n"
    for account in instance_data['accounts']:
        report += f"| {account['account_id']} | {account['instance_count']} |\n"
    report += f"\n![Instances by Account]({os.path.basename(account_graph)})\n\n"

    report += "### 3.2 리전별 인스턴스 분포\n\n"
    report += "| Region | Instance Count |\n"
    report += "|--------|----------------|\n"
    for region in instance_data['regions']:
        report += f"| {region['region']} | {region['instance_count']} |\n"
    report += f"\n![Instances by Region]({os.path.basename(region_graph)})\n\n"

    report += "### 3.3 인스턴스 클래스 분포\n\n"
    report += "| Instance Class | Count |\n"
    report += "|----------------|-------|\n"
    for instance_class, count in sorted(instance_data['instance_classes'].items()):
        report += f"| {instance_class} | {count} |\n"
    report += f"\n![Instance Class Distribution]({os.path.basename(class_graph)})\n\n"

    # 4. 성능 메트릭 분석
    report += "## 4. 성능 메트릭 분석\n\n"
    report += f"분석 기간: {start_date} ~ {end_date}\n"
    report += f"총 데이터 포인트: {len(prometheus_data)}개\n\n"

    report += "### 4.1 인스턴스별 평균 성능 지표\n\n"
    for instance in sorted(prometheus_data[0]['metrics'].keys()):
        report += f"#### {instance}\n\n"
        avg_cpu = sum(d['metrics'][instance]['rds_cpu_usage_percent_average']['avg'] for d in prometheus_data) / len(
            prometheus_data)
        avg_read_iops = sum(d['metrics'][instance]['rds_read_iops_average']['avg'] for d in prometheus_data) / len(
            prometheus_data)
        avg_write_iops = sum(d['metrics'][instance]['rds_write_iops_average']['avg'] for d in prometheus_data) / len(
            prometheus_data)
        avg_connections = sum(
            d['metrics'][instance]['rds_database_connections_average']['avg'] for d in prometheus_data) / len(
            prometheus_data)

        report += f"- 평균 CPU 사용률: {avg_cpu:.2f}%\n"
        report += f"- 평균 Read IOPS: {avg_read_iops:.2f}\n"
        report += f"- 평균 Write IOPS: {avg_write_iops:.2f}\n"
        report += f"- 평균 데이터베이스 연결 수: {avg_connections:.2f}\n\n"

    report += "### 4.2 성능 그래프\n\n"
    report += f"#### CPU 사용률\n\n![CPU Usage Graph]({os.path.basename(cpu_graph)})\n\n"
    report += f"#### IOPS\n\n![IOPS Graph]({os.path.basename(iops_graph)})\n\n"

    # 5. ChatGPT 분석
    report += "## 5. 종합 분석 및 인사이트\n\n"
    report += analysis + "\n\n"

    return report

async def create_zip_archive(report_dir: str, report_file: str, graph_files: Set[str]) -> str:
    """리포트와 그래프들을 ZIP 파일로 압축"""
    try:
        # ZIP 파일명 생성
        zip_filename = report_file.replace('.md', '.zip')
        zip_filepath = os.path.join(report_dir, zip_filename)

        # ZIP 파일 생성
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 리포트 파일 추가
            report_filepath = os.path.join(report_dir, report_file)
            zipf.write(report_filepath, os.path.basename(report_filepath))

            # 그래프 파일들 추가
            for graph_file in graph_files:
                graph_filepath = os.path.join(report_dir, graph_file)
                if os.path.exists(graph_filepath):
                    zipf.write(graph_filepath, os.path.basename(graph_filepath))

        logger.info("Successfully created ZIP archive", zip_file=zip_filepath)
        return zip_filepath

    except Exception as e:
        logger.error(f"Error creating ZIP archive: {str(e)}")
        raise

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

        # end_date를 기준으로 리포트 디렉토리 생성
        report_date = datetime.strptime(end_date, "%Y-%m-%d")
        report_dir = report_settings.get_report_dir(report_date)
        os.makedirs(report_dir, exist_ok=True)

        try:
            # 모든 데이터 병렬로 가져오기
            instance_data_coro = get_cached_instance_statistics_wrapper()
            prometheus_data_coro = get_cached_prometheus_data_wrapper(start_date, end_date)
            monthly_changes_coro = get_monthly_instance_changes(start_date, end_date)

            logger.info(f"Fetching data for period: {start_date} to {end_date}")

            # 비동기 작업 실행
            results = await asyncio.gather(
                instance_data_coro,
                prometheus_data_coro,
                monthly_changes_coro,
                return_exceptions=True
            )

            # 결과 확인 및 예외 처리
            instance_data, prometheus_data, monthly_changes = results

            # 각 결과 확인
            if isinstance(instance_data, Exception):
                logger.error(f"Failed to get instance statistics: {str(instance_data)}")
                instance_data = None

            if isinstance(prometheus_data, Exception):
                logger.error(f"Failed to get prometheus data: {str(prometheus_data)}")
                prometheus_data = None

            if isinstance(monthly_changes, Exception):
                logger.error(f"Failed to get monthly changes: {str(monthly_changes)}")
                monthly_changes = None

            if not prometheus_data:
                raise HTTPException(status_code=404, detail="No prometheus data found for the specified date range")

            if not instance_data:
                raise HTTPException(status_code=404, detail="No instance statistics data available")

        except Exception as e:
            logger.error(f"Error gathering data: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to gather required data")

        try:
            # 병렬로 그래프 생성 및 분석 수행
            graph_results = await asyncio.gather(
                create_instance_graphs(instance_data, end_date, report_dir),
                create_prometheus_graphs(prometheus_data, start_date, end_date, report_dir),
                get_chatgpt_analysis(instance_data, prometheus_data),
                return_exceptions=True
            )

            (account_graph, region_graph, class_graph), (cpu_graph, iops_graph), analysis = graph_results

            # 결과 확인
            for result in graph_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in graph generation or analysis: {str(result)}")
                    raise HTTPException(status_code=500, detail="Failed to generate graphs or analysis")

        except Exception as e:
            logger.error(f"Error in graph generation or analysis: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate report components")

        try:
            # 리포트 생성
            report = await create_integrated_report(
                instance_data=instance_data,
                prometheus_data=prometheus_data,
                date=end_date,
                start_date=start_date,
                end_date=end_date,
                account_graph=account_graph,
                region_graph=region_graph,
                class_graph=class_graph,
                cpu_graph=cpu_graph,
                iops_graph=iops_graph,
                analysis=analysis,
                monthly_changes=monthly_changes
            )

            filename = f"integrated_rds_report_{start_date}_{end_date}.md"
            file_path = os.path.join(report_dir, filename)

            # 리포트 파일 저장
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(report)

            # 그래프 파일 리스트 생성
            graph_files = [
                account_graph,
                region_graph,
                class_graph,
                cpu_graph,
                iops_graph
            ]

            # ZIP 파일 생성
            zip_file_path = await create_zip_archive(report_dir, filename, graph_files)

            logger.info("Report generated successfully",
                        report_path=file_path,
                        zip_path=zip_file_path)

            return {
                "message": "Integrated RDS report generated successfully",
                "report_path": file_path,
                "zip_path": zip_file_path,
                "data_status": {
                    "instance_data": "success" if instance_data else "failed",
                    "prometheus_data": "success" if prometheus_data else "failed",
                    "monthly_changes": "success" if monthly_changes else "failed"
                }
            }

        except Exception as e:
            logger.error(f"Error in report generation or ZIP creation: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate final report or create ZIP")

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