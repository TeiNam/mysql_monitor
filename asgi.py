import uvicorn
from contextlib import asynccontextmanager
from configs.app_conf import app_settings
from apis import app

@asynccontextmanager
async def lifespan(app):
    # 시작 시 실행할 코드
    print("Application is starting up")
    yield
    # 종료 시 실행할 코드
    print("Application is shutting down")

app.router.lifespan_context = lifespan

__all__ = ['app']

if __name__ == "__main__":
    uvicorn.run(
        "asgi:app",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=True
    )