# cleanup.py
import os
import shutil
from datetime import datetime, timedelta
import pytz
import logging
from typing import Dict, List
from configs.report_conf import report_settings

logger = logging.getLogger(__name__)
kst = pytz.timezone('Asia/Seoul')


class ReportCleaner:
    def __init__(self, base_dir: str = report_settings.BASE_REPORT_DIR, retention_days: int = 31):
        self.base_dir = base_dir
        self.retention_days = retention_days

    async def cleanup(self) -> Dict[str, List[str]]:
        """
        오래된 리포트 파일과 폴더를 정리하는 함수

        Returns:
            Dict[str, List[str]]: 삭제된 항목들의 목록
        """
        try:
            cutoff_date = datetime.now(kst) - timedelta(days=self.retention_days)
            deleted_items = {
                "files": [],
                "folders": [],
                "zip_files": []
            }

            # 디렉토리 내 모든 항목 검사
            for item in os.listdir(self.base_dir):
                item_path = os.path.join(self.base_dir, item)
                try:
                    item_time = datetime.fromtimestamp(os.path.getctime(item_path), kst)

                    if item_time < cutoff_date:
                        await self._process_item(item_path, item, deleted_items)

                except Exception as item_err:
                    logger.error(f"Error processing {item_path}: {str(item_err)}")
                    continue

            # 결과 로깅
            self._log_cleanup_results(deleted_items)
            return deleted_items

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
            raise

    async def _process_item(self, item_path: str, item_name: str, deleted_items: Dict[str, List[str]]):
        """개별 파일/폴더 처리"""
        try:
            if os.path.isfile(item_path):
                await self._handle_file(item_path, item_name, deleted_items)
            elif os.path.isdir(item_path):
                await self._handle_directory(item_path, item_name, deleted_items)

        except Exception as e:
            logger.error(f"Failed to process {item_path}: {str(e)}")

    async def _handle_file(self, file_path: str, file_name: str, deleted_items: Dict[str, List[str]]):
        """파일 처리"""
        try:
            os.remove(file_path)
            if file_name.endswith('.zip'):
                deleted_items["zip_files"].append(file_name)
            else:
                deleted_items["files"].append(file_name)
            logger.debug(f"Deleted file: {file_name}")

        except Exception as e:
            logger.error(f"Failed to delete file {file_name}: {str(e)}")

    async def _handle_directory(self, dir_path: str, dir_name: str, deleted_items: Dict[str, List[str]]):
        """디렉토리 처리"""
        try:
            # 날짜 형식의 폴더인지 확인 (YYYY-MM-DD)
            datetime.strptime(dir_name, "%Y-%m-%d")
            shutil.rmtree(dir_path)
            deleted_items["folders"].append(dir_name)
            logger.debug(f"Deleted directory: {dir_name}")

        except ValueError:
            # 날짜 형식이 아닌 폴더는 무시
            logger.debug(f"Skipping non-date directory: {dir_name}")
        except Exception as e:
            logger.error(f"Failed to delete directory {dir_name}: {str(e)}")

    def _log_cleanup_results(self, deleted_items: Dict[str, List[str]]):
        """클린업 결과 로깅"""
        total_deleted = sum(len(items) for items in deleted_items.values())

        if total_deleted > 0:
            logger.info("Cleanup completed",
                        total_deleted=total_deleted,
                        deleted_zip_files=len(deleted_items["zip_files"]),
                        deleted_folders=len(deleted_items["folders"]),
                        deleted_files=len(deleted_items["files"]))

            logger.debug("Deleted items details",
                         zip_files=deleted_items["zip_files"],
                         folders=deleted_items["folders"],
                         files=deleted_items["files"])
        else:
            logger.info("No items needed cleanup")