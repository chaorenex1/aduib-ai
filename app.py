import asyncio
from multiprocessing.spawn import freeze_support

from app_factory import create_app

app = None
if not app:
    app = create_app()


async def run_app(**kwargs):
    import uvicorn

    config = uvicorn.Config(app=app, host=app.config.APP_HOST, port=app.config.APP_PORT, **kwargs)
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    if app:
        freeze_support()
        import uvicorn

        asyncio.run(run_app())
