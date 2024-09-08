import os
import logging
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

IGNORE_LOGGERS = ['asyncmy']
IGNORE_MESSAGES = ["'INFORMATION_SCHEMA.PROCESSLIST' is deprecated"]


class IgnoreFilter(logging.Filter):
    def filter(self, record):
        return not (
                record.name in IGNORE_LOGGERS or
                any(msg in record.getMessage() for msg in IGNORE_MESSAGES)
        )


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    root_logger.setLevel(LOG_LEVEL)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    ignore_filter = IgnoreFilter()
    console_handler.addFilter(ignore_filter)
    file_handler.addFilter(ignore_filter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger('asyncmy').setLevel(logging.WARNING)


setup_logging()


def get_logger(name):
    return logging.getLogger(name)