import matplotlib.pyplot as plt
import os
from io import BytesIO
import aiofiles
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger()

async def save_graph(fig, path):
    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    async with aiofiles.open(path, 'wb') as f:
        await f.write(buf.getvalue())

async def create_instance_graphs(data: Dict[str, Any], date: str, report_dir: str):
    try:
        # 계정별 그래프
        fig, ax = plt.subplots(figsize=(10, 6))
        accounts = [account['account_id'] for account in data['accounts']]
        instance_counts = [account['instance_count'] for account in data['accounts']]
        ax.bar(accounts, instance_counts)
        ax.set_title("Instances by Account")
        ax.set_xlabel("Account ID")
        ax.set_ylabel("Instance Count")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        account_graph_path = os.path.join(report_dir, f"account_graph_{date}.png")
        await save_graph(fig, account_graph_path)
        plt.close(fig)

        # 리전별 그래프
        fig, ax = plt.subplots(figsize=(8, 6))
        regions = [region['region'] for region in data['regions']]
        region_counts = [region['instance_count'] for region in data['regions']]
        ax.pie(region_counts, labels=regions, autopct='%1.1f%%', startangle=90)
        ax.set_title("Instances by Region")
        plt.axis('equal')
        region_graph_path = os.path.join(report_dir, f"region_graph_{date}.png")
        await save_graph(fig, region_graph_path)
        plt.close(fig)

        # 인스턴스 클래스별 그래프
        fig, ax = plt.subplots(figsize=(12, 6))
        classes = list(data['instance_classes'].keys())
        class_counts = list(data['instance_classes'].values())
        ax.bar(classes, class_counts)
        ax.set_title("Instance Class Distribution")
        ax.set_xlabel("Instance Class")
        ax.set_ylabel("Count")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        class_graph_path = os.path.join(report_dir, f"class_graph_{date}.png")
        await save_graph(fig, class_graph_path)
        plt.close(fig)

        return account_graph_path, region_graph_path, class_graph_path
    except Exception as e:
        logger.error("Error creating instance graphs", error=str(e))
        raise

async def create_prometheus_graphs(data: List[Dict[str, Any]], start_date: str, end_date: str, report_dir: str):
    try:
        # CPU 사용률 그래프
        fig, ax = plt.subplots(figsize=(12, 6))
        for instance in data[0]['metrics']:
            dates = [d['date'] for d in data]
            cpu_usage = [d['metrics'][instance]['rds_cpu_usage_percent_average']['avg'] for d in data]
            ax.plot(dates, cpu_usage, label=instance)
        ax.set_title("Average CPU Usage by Instance")
        ax.set_xlabel("Date")
        ax.set_ylabel("CPU Usage (%)")
        ax.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        cpu_graph_path = os.path.join(report_dir, f"cpu_usage_{start_date}_{end_date}.png")
        await save_graph(fig, cpu_graph_path)
        plt.close(fig)

        # IOPS 그래프
        fig, ax = plt.subplots(figsize=(12, 6))
        for instance in data[0]['metrics']:
            dates = [d['date'] for d in data]
            read_iops = [d['metrics'][instance]['rds_read_iops_average']['avg'] for d in data]
            write_iops = [d['metrics'][instance]['rds_write_iops_average']['avg'] for d in data]
            ax.plot(dates, read_iops, label=f"{instance} Read")
            ax.plot(dates, write_iops, label=f"{instance} Write")
        ax.set_title("Average Read and Write IOPS by Instance")
        ax.set_xlabel("Date")
        ax.set_ylabel("IOPS")
        ax.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        iops_graph_path = os.path.join(report_dir, f"iops_{start_date}_{end_date}.png")
        await save_graph(fig, iops_graph_path)
        plt.close(fig)

        return cpu_graph_path, iops_graph_path
    except Exception as e:
        logger.error("Error creating Prometheus graphs", error=str(e))
        raise