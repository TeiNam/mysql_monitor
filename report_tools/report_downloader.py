import os
import logging
import pytz
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
import zipfile
from configs.report_conf import report_settings
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# KST 시간대 설정
kst = pytz.timezone('Asia/Seoul')

@router.get("/download-report")
async def download_report(date: str = Query(..., description="Report date in YYYY-MM-DD format")):
    try:
        report_date = datetime.strptime(date, "%Y-%m-%d")
        report_dir = report_settings.get_report_dir(report_date)

        if not os.path.exists(report_dir):
            raise HTTPException(status_code=404, detail="Report not found for the specified date")

        zip_filename = f"report_{date}.zip"
        zip_path = os.path.join(report_settings.BASE_REPORT_DIR, zip_filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(report_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, report_dir)
                    zipf.write(file_path, arcname)

        return FileResponse(
            path=zip_path,
            filename=zip_filename,
            media_type='application/zip'
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    except Exception as e:
        logger.exception("Error creating zip file", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create zip file: {str(e)}")