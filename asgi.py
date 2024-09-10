import uvicorn
from configs.app_conf import app_settings
from apis.main import app  # apis/main.py에서 app을 직접 가져옵니다.

__all__ = ['app']

if __name__ == "__main__":
    uvicorn.run(
        "asgi:app",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=True
    )