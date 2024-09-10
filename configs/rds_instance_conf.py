import os
import json
from typing import List
from pydantic_settings import BaseSettings
from configs.mongo_conf import mongo_settings

class RDSInstanceSettings(BaseSettings):
    AWS_REGIONS: str

    class Config:
        env_file = ".env"
        extra = "ignore"

    @classmethod
    def get_regions(cls) -> List[str]:
        regions_str = os.getenv('AWS_REGIONS')
        if not regions_str:
            raise ValueError("AWS_REGIONS is not set in the environment variables.")
        try:
            return json.loads(regions_str)
        except json.JSONDecodeError:
            raise ValueError("AWS_REGIONS is not a valid JSON string.")

rds_settings = RDSInstanceSettings()

AWS_REGIONS = rds_settings.get_regions()
AWS_RDS_INSTANCE_ALL_STAT_COLLECTION = mongo_settings.MONGO_RDS_INSTANCE_ALL_STAT_COLLECTION