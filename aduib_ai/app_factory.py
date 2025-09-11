import asyncio
import contextlib
import logging
import os
import pathlib
import time
from typing import AsyncIterator

from fastapi.routing import APIRoute

from aduib_app import AduibAIApp
from component.cache.redis_cache import init_cache
from component.log.app_logging import init_logging
from component.storage.base_storage import init_storage
from configs import config
from controllers.route import api_router
from libs.context import LoggingMiddleware, TraceIdContextMiddleware, ApiKeyContextMiddleware
from utils.snowflake_id import init_idGenerator

log=logging.getLogger(__name__)


def create_app_with_configs()->AduibAIApp:
    def custom_generate_unique_id(route: APIRoute) -> str:
        return f"{route.tags[0]}-{route.name}"

    app = AduibAIApp(
        title=config.APP_NAME,
        generate_unique_id_function=custom_generate_unique_id,
        debug=config.DEBUG,
        lifespan=lifespan
    )
    app.config=config
    if config.APP_HOME:
        app.app_home = config.APP_HOME
    else:
        app.app_home = os.getenv("user.home", str(pathlib.Path.home())) + f"/.{config.APP_NAME.lower()}"
    app.include_router(api_router, prefix="/v1")
    if config.DEBUG:
        log.warning("Running in debug mode, this is not recommended for production use.")
        app.add_middleware(LoggingMiddleware)
    app.add_middleware(TraceIdContextMiddleware)
    app.add_middleware(ApiKeyContextMiddleware)
    return app


def create_app()->AduibAIApp:
    start_time = time.perf_counter()
    app = create_app_with_configs()
    init_logging(app)
    init_apps(app)
    end_time = time.perf_counter()
    log.info(f"App home directory: {app.app_home}")
    log.info(f"Finished create_app ({round((end_time - start_time) * 1000, 2)} ms)")
    return app


def init_apps(app: AduibAIApp):
    """
    Initialize the app with necessary configurations and middlewares.
    :param app: AduibAIApp instance
    """
    log.info("Initializing middlewares")
    init_idGenerator(app)
    init_cache(app)
    init_storage(app)
    log.info("middlewares initialized successfully")


async def run_service_register(app: AduibAIApp):
    registry_config = {
        "server_addresses": app.config.NACOS_SERVER_ADDR,
        "namespace": app.config.NACOS_NAMESPACE,
        "group_name": app.config.NACOS_GROUP,
        "username": app.config.NACOS_USERNAME,
        "password": app.config.NACOS_PASSWORD,
        "DISCOVERY_SERVICE_ENABLED": app.config.DISCOVERY_SERVICE_ENABLED,
        "DISCOVERY_SERVICE_TYPE": app.config.DISCOVERY_SERVICE_TYPE,
        "SERVICE_TRANSPORT_SCHEME": app.config.SERVICE_TRANSPORT_SCHEME,
        "APP_NAME": app.config.APP_NAME,
    }
    from aduib_rpc.server.request_excution.service_call import load_service_plugins
    from aduib_rpc.discover.registry.registry_factory import ServiceRegistryFactory
    from aduib_rpc.discover.service import AduibServiceFactory
    service = await ServiceRegistryFactory.start_service_registry(registry_config)
    factory = AduibServiceFactory(service_instance=service)
    load_service_plugins('rpc.client')
    await factory.run_server()


@contextlib.asynccontextmanager
async def lifespan(app: AduibAIApp) -> AsyncIterator[None]:
    log.info("Lifespan is starting")
    asyncio.create_task(run_service_register(app))
    yield None
