import os
import shutil
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from configs.report_conf import report_settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def is_old_file(file_path, days=31):
    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
    return datetime.now() - file_time > timedelta(days=days)

@router.post("/cleanup-old-files")
async def cleanup_old_files(days: int = 31):
    try:
        base_dir = report_settings.BASE_REPORT_DIR
        deleted_files = 0
        deleted_folders = 0

        # ZIP 파일 정리
        for filename in os.listdir(base_dir):
            if filename.endswith('.zip'):
                file_path = os.path.join(base_dir, filename)
                if is_old_file(file_path, days):
                    os.remove(file_path)
                    deleted_files += 1
                    logger.info(f"Deleted old ZIP file: {filename}")

        # 리포트 폴더 정리
        for foldername in os.listdir(base_dir):
            folder_path = os.path.join(base_dir, foldername)
            if os.path.isdir(folder_path) and is_old_file(folder_path, days):
                shutil.rmtree(folder_path)
                deleted_folders += 1
                logger.info(f"Deleted old report folder: {foldername}")

        return {
            "message": "Cleanup completed successfully",
            "deleted_files": deleted_files,
            "deleted_folders": deleted_folders
        }
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")