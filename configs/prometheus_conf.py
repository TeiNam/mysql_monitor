from pydantic_settings import BaseSettings
from typing import List

class PrometheusSettings(BaseSettings):
    PROMETHEUS_URL: str = "https://mgmt.prom.devops.torder.tech"
    METRICS: List[str] = [
        "rds_cpu_usage_percent_average",
        "rds_read_iops_average",
        "rds_write_iops_average",
        "rds_dbload_noncpu_average",
        "rds_database_connections_average"
    ]
    DB_IDENTIFIERS: List[str] = [
        "orderservice",
        "prd-orderservice-read-instance-6",
        "prd-orderservice-read-instance-7",
        "prd-orderservice-read-instance-8",
        "prd-orderservice-read-lookup-instance-1",
        "orderservice-us-east",
        "sg-orderservice",
        "orderservice-sydney",
        "prd-connect-waiting-instance-1",
        "prd-connect-waiting-instance-2",
        "prd-connect-aurora-reader",
        "prd-connect-aurora-cluster-01"
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"