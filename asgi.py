import uvicorn
import asyncio
from configs.app_conf import app_settings
from apis import app
from collectors.collectors import main as collectors_main

__all__ = ['app']

async def start_collectors():
    await collectors_main()

@app.on_event("startup")
async def startup_event():
    # Collectors를 백그라운드 태스크로 실행
    asyncio.create_task(start_collectors())

if __name__ == "__main__":
    uvicorn.run(
        "asgi:app",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=True
    )