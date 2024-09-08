import os
import logging
from logging.handlers import RotatingFileHandler

# 프로젝트 루트 디렉토리 경로 (이 파일의 상위 디렉토리로 가정)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

IGNORE_LOGGERS = ['asyncmy']  # 무시할 로거 이름 리스트
IGNORE_MESSAGES = ["'INFORMATION_SCHEMA.PROCESSLIST' is deprecated"]  # 무시할 메시지 리스트

class IgnoreFilter(logging.Filter):
    def filter(self, record):
        return not (
            record.name in IGNORE_LOGGERS or
            any(msg in record.getMessage() for msg in IGNORE_MESSAGES)
        )

def setup_logging():
    # logs 디렉토리 생성
    os.makedirs(LOG_DIR, exist_ok=True)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # 파일 핸들러 설정 (로그 로테이션 포함)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # 필터 추가
    ignore_filter = IgnoreFilter()
    console_handler.addFilter(ignore_filter)
    file_handler.addFilter(ignore_filter)

    # 핸들러 추가
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.info(f"Logging setup completed. Log file: {LOG_FILE}")

if __name__ == "__main__":
    setup_logging()
    logging.info("This is a test log message.")