import logging
import time

from fastapi.routing import APIRoute

from aduib_app import AduibAIApp
from component.cache.redis_cache import init_cache
from component.log.app_logging import init_logging
from configs import config
from controllers.route import api_router
from utils.snowflake_id import init_idGenerator
from libs.context import LoggingMiddleware

log=logging.getLogger(__name__)


def create_app_with_configs()->AduibAIApp:
    def custom_generate_unique_id(route: APIRoute) -> str:
        return f"{route.tags[0]}-{route.name}"

    app = AduibAIApp(
        title=config.APP_NAME,
        generate_unique_id_function=custom_generate_unique_id,
        debug=config.DEBUG,
    )
    app.config=config
    app.include_router(api_router, prefix="/v1")
    if config.DEBUG:
        log.warning("Running in debug mode, this is not recommended for production use.")
        app.add_middleware(LoggingMiddleware)
    return app


def create_app()->AduibAIApp:
    start_time = time.perf_counter()
    init_logging()
    init_idGenerator()
    app = create_app_with_configs()
    init_apps(app)
    end_time = time.perf_counter()
    log.info(f"Finished create_app ({round((end_time - start_time) * 1000, 2)} ms)")
    return app


def init_apps(app: AduibAIApp):
    """
    Initialize the app with necessary configurations and middlewares.
    :param app: AduibAIApp instance
    """
    log.info("Initializing middlewares")
    init_cache(app)
    log.info("middlewares initialized successfully")
