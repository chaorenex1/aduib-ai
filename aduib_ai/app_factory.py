import logging
import time

from fastapi.routing import APIRoute

from .aduib_app import AduibAIApp
from .component.log.app_logging import init_logging
from .configs import config
from .controllers.route import api_router
from .utils.snowflake_id import init_idGenerator

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
    app.include_router(api_router, prefix="/aduib_ai/v1")
    return app


def create_app()->AduibAIApp:
    start_time = time.perf_counter()
    init_logging()
    init_idGenerator()
    app = create_app_with_configs()
    end_time = time.perf_counter()
    log.info(f"Finished create_app ({round((end_time - start_time) * 1000, 2)} ms)")
    return app