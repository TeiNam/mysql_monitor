from apis import app as application
import uvicorn
from configs.app_conf import app_settings

__all__ = ['application']

if __name__ == "__main__":
    uvicorn.run(
        "asgi:application",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=True
    )
