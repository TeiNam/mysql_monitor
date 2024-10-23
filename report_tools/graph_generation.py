# graph_generation.py

import os
from typing import Dict, Any, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import structlog

logger = structlog.get_logger()


async def create_instance_graphs(instance_data: Dict[str, Any], date: str, report_dir: str) -> Tuple[str, str, str]:
    """인스턴스 관련 그래프들을 생성하는 함수"""
    try:
        # 1. 계정별 인스턴스 분포 그래프
        account_graph = await create_account_distribution_graph(instance_data, date, report_dir)

        # 2. 리전별 인스턴스 분포 그래프
        region_graph = await create_region_distribution_graph(instance_data, date, report_dir)

        # 3. 인스턴스 클래스 분포 그래프
        class_graph = await create_instance_class_distribution_graph(instance_data, date, report_dir)

        return account_graph, region_graph, class_graph

    except Exception as e:
        logger.error(f"Error creating instance graphs: {str(e)}")
        raise


async def create_account_distribution_graph(instance_data: Dict[str, Any], date: str, report_dir: str) -> str:
    """계정별 인스턴스 분포 그래프 생성"""
    plt.figure(figsize=(12, 6))
    accounts = [acc['account_id'] for acc in instance_data['accounts']]
    counts = [acc['instance_count'] for acc in instance_data['accounts']]

    # 막대 그래프 생성
    sns.barplot(x=accounts, y=counts)
    plt.xticks(rotation=45, ha='right')
    plt.title('Account-wise Instance Distribution')
    plt.xlabel('Account ID')
    plt.ylabel('Number of Instances')

    # 그래프 저장
    filename = f"account_distribution_{date}.png"
    filepath = os.path.join(report_dir, filename)
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close()

    return filepath


async def create_region_distribution_graph(instance_data: Dict[str, Any], date: str, report_dir: str) -> str:
    """리전별 인스턴스 분포 그래프 생성"""
    plt.figure(figsize=(12, 6))
    regions = [reg['region'] for reg in instance_data['regions']]
    counts = [reg['instance_count'] for reg in instance_data['regions']]

    # 막대 그래프 생성
    sns.barplot(x=regions, y=counts)
    plt.xticks(rotation=45, ha='right')
    plt.title('Region-wise Instance Distribution')
    plt.xlabel('Region')
    plt.ylabel('Number of Instances')

    # 그래프 저장
    filename = f"region_distribution_{date}.png"
    filepath = os.path.join(report_dir, filename)
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close()

    return filepath


async def create_instance_class_distribution_graph(instance_data: Dict[str, Any], date: str, report_dir: str) -> str:
    """인스턴스 클래스 분포 그래프 생성"""
    plt.figure(figsize=(12, 6))
    classes = list(instance_data['instance_classes'].keys())
    counts = list(instance_data['instance_classes'].values())

    # 막대 그래프 생성
    sns.barplot(x=classes, y=counts)
    plt.xticks(rotation=45, ha='right')
    plt.title('Instance Class Distribution')
    plt.xlabel('Instance Class')
    plt.ylabel('Number of Instances')

    # 그래프 저장
    filename = f"class_distribution_{date}.png"
    filepath = os.path.join(report_dir, filename)
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close()

    return filepath


async def create_prometheus_graphs(prometheus_data: List[Dict[str, Any]],
                                   start_date: str, end_date: str,
                                   report_dir: str) -> Tuple[str, str]:
    """Prometheus 메트릭 그래프 생성"""
    try:
        # CPU 사용률 그래프
        cpu_graph = await create_cpu_usage_graph(prometheus_data, start_date, end_date, report_dir)

        # IOPS 그래프
        iops_graph = await create_iops_graph(prometheus_data, start_date, end_date, report_dir)

        return cpu_graph, iops_graph

    except Exception as e:
        logger.error(f"Error creating prometheus graphs: {str(e)}")
        raise


async def create_cpu_usage_graph(prometheus_data: List[Dict[str, Any]],
                                 start_date: str, end_date: str,
                                 report_dir: str) -> str:
    """CPU 사용률 그래프 생성"""
    plt.figure(figsize=(15, 8))

    dates = [d['date'] for d in prometheus_data]
    for instance in prometheus_data[0]['metrics']:
        cpu_values = [d['metrics'][instance]['rds_cpu_usage_percent_average']['avg']
                      for d in prometheus_data]
        plt.plot(dates, cpu_values, label=instance, marker='o')

    plt.title('CPU Usage Over Time')
    plt.xlabel('Date')
    plt.ylabel('CPU Usage (%)')
    plt.xticks(rotation=45, ha='right')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True)

    filename = f"cpu_usage_{start_date}_{end_date}.png"
    filepath = os.path.join(report_dir, filename)
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close()

    return filepath


async def create_iops_graph(prometheus_data: List[Dict[str, Any]],
                            start_date: str, end_date: str,
                            report_dir: str) -> str:
    """IOPS 그래프 생성"""
    plt.figure(figsize=(15, 8))

    dates = [d['date'] for d in prometheus_data]
    for instance in prometheus_data[0]['metrics']:
        read_iops = [d['metrics'][instance]['rds_read_iops_average']['avg']
                     for d in prometheus_data]
        write_iops = [d['metrics'][instance]['rds_write_iops_average']['avg']
                      for d in prometheus_data]

        plt.plot(dates, read_iops, label=f"{instance} (Read)", linestyle='-', marker='o')
        plt.plot(dates, write_iops, label=f"{instance} (Write)", linestyle='--', marker='s')

    plt.title('Read/Write IOPS Over Time')
    plt.xlabel('Date')
    plt.ylabel('IOPS')
    plt.xticks(rotation=45, ha='right')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True)

    filename = f"iops_{start_date}_{end_date}.png"
    filepath = os.path.join(report_dir, filename)
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close()

    return filepath