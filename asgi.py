import uvicorn
from configs.app_conf import app_settings
from apis import app

__all__ = ['app']

if __name__ == "__main__":
    uvicorn.run(
        "asgi:app",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=True
    )