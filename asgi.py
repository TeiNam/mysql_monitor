import uvicorn
import asyncio
from configs.app_conf import app_settings
from apis import app as application
from collectors.collectors import main as collectors_main

__all__ = ['application']

async def start_collectors():
    await collectors_main()

@application.on_event("startup")
async def startup_event():
    await asyncio.create_task(start_collectors())

if __name__ == "__main__":
    uvicorn.run(
        "asgi:application",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=True
    )