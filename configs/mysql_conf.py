import os
from dotenv import load_dotenv

load_dotenv()

# MySQL 슬로우 쿼리 설정
EXEC_TIME = int(os.getenv('EXEC_TIME', 2))  # 기본값 1초

# 기타 MySQL 관련 설정들
MYSQL_DEFAULT_PORT = 3306
MYSQL_CONNECTION_TIMEOUT = int(os.getenv('MYSQL_CONNECTION_TIMEOUT', 10))
MYSQL_MAX_POOL_SIZE = int(os.getenv('MYSQL_MAX_POOL_SIZE', 1))