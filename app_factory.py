import asyncio
import contextlib
import logging
import os
import pathlib
import time
from typing import AsyncIterator

from aduib_rpc.utils.net_utils import NetUtils
from fastapi.routing import APIRoute

from aduib_app import AduibAIApp
from component.cache.redis_cache import init_cache
from component.log.app_logging import init_logging
from component.storage.base_storage import init_storage
from configs import config
from controllers.route import api_router
from libs.context import LoggingMiddleware, TraceIdContextMiddleware, ApiKeyContextMiddleware
from utils.snowflake_id import init_idGenerator

log = logging.getLogger(__name__)


def create_app_with_configs() -> AduibAIApp:
    def custom_generate_unique_id(route: APIRoute) -> str:
        return f"{route.tags[0]}-{route.name}"

    app = AduibAIApp(
        title=config.APP_NAME,
        generate_unique_id_function=custom_generate_unique_id,
        debug=config.DEBUG,
        lifespan=lifespan,
    )
    app.config = config
    if config.APP_HOME:
        app.app_home = config.APP_HOME
    else:
        app.app_home = os.getenv("user.home", str(pathlib.Path.home())) + f"/.{config.APP_NAME.lower()}"
    app.include_router(api_router, prefix="/v1")
    if config.DEBUG:
        log.warning("Running in debug mode, this is not recommended for production use.")
        app.add_middleware(LoggingMiddleware)
    # app.add_middleware(TraceIdContextMiddleware)
    app.add_middleware(ApiKeyContextMiddleware)
    return app


def create_app() -> AduibAIApp:
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
    from event.event_manager import EventManager
    from event.event_manager import event_manager_context

    event_manager = EventManager()
    app.extensions["event_manager"] = event_manager
    event_manager_context.set(event_manager)
    from event.rag.rag_event import paragraph_rag_from_web_memo, qa_rag_from_conversation_message
    from event.agent.agent_event import agent_from_conversation_message

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
    from aduib_rpc.discover.registry.registry_factory import ServiceRegistryFactory
    from aduib_rpc.discover.entities import ServiceInstance
    from aduib_rpc.utils.constant import AIProtocols
    from aduib_rpc.utils.constant import TransportSchemes
    from aduib_rpc.discover.service import AduibServiceFactory
    from aduib_rpc.server.rpc_execution.service_call import load_service_plugins
    ip, port = NetUtils.get_ip_and_free_port()
    service_registry = ServiceRegistryFactory.start_service_discovery(registry_config)
    rpc_service_info = ServiceInstance(service_name=registry_config.get('APP_NAME', 'aduib-rpc'), host=ip, port=port,
                                       protocol=AIProtocols.AduibRpc, weight=1,
                                       scheme=config.SERVICE_TRANSPORT_SCHEME or TransportSchemes.GRPC)
    if rpc_service_info and config.RPC_SERVICE_PORT>0:
        rpc_service_info.port=config.RPC_SERVICE_PORT

    factory = AduibServiceFactory(service_instance=rpc_service_info)
    load_service_plugins('rpc.service')
    load_service_plugins('rpc.client')
    if rpc_service_info and config.DOCKER_ENV:
        rpc_service_info = ServiceInstance(service_name=rpc_service_info.service_name, host=config.RPC_SERVICE_HOST, port=rpc_service_info.port,
                                       protocol=rpc_service_info.protocol, weight=rpc_service_info.weight,
                                       scheme=rpc_service_info.scheme)
    aduib_ai_service = rpc_service_info.__deepcopy__()
    aduib_ai_service.service_name=config.APP_NAME+"-app"
    if config.DOCKER_ENV:
        aduib_ai_service.host=config.RPC_SERVICE_HOST
        aduib_ai_service.port=config.APP_PORT
    else:
        aduib_ai_service.host=ip
        aduib_ai_service.port=config.APP_PORT
    await service_registry.register_service(rpc_service_info)
    await service_registry.register_service(aduib_ai_service)
    await factory.run_server()


@contextlib.asynccontextmanager
async def lifespan(app: AduibAIApp) -> AsyncIterator[None]:
    log.info("Lifespan is starting")
    asyncio.create_task(run_service_register(app))
    from event.event_manager import EventManager

    event_manager: EventManager = app.extensions.get("event_manager")
    if event_manager:
        event_manager.start()
        log.info("Event manager started")

    yield None

    # Shutdown logic
    log.info("Application is shutting down, cleaning up resources...")

    # Stop event manager
    if event_manager:
        try:
            await event_manager.stop()
            log.info("Event manager stopped")
        except Exception as e:
            log.error(f"Error stopping event manager: {e}")

    # Close database connections
    try:
        from models.engine import engine
        engine.dispose()
        log.info("Database connections closed")
    except Exception as e:
        log.error(f"Error closing database connections: {e}")

    # Clear HTTP client cache
    try:
        from libs.cache import in_memory_llm_clients_cache
        in_memory_llm_clients_cache.clear()
        log.info("HTTP client cache cleared")
    except Exception as e:
        log.error(f"Error clearing HTTP client cache: {e}")

    log.info("Application shutdown complete")
