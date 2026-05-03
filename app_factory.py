import asyncio
import contextlib
import logging
import os
import pathlib
import time
from collections.abc import AsyncIterator

from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from aduib_app import AduibAIApp
from component.cache.redis_cache import init_cache
from component.log.app_logging import init_logging
from component.storage.base_storage import init_storage
from configs import config
from controllers.route import api_router
from libs.context import (
    ApiKeyContextMiddleware,
    LoggingMiddleware,
    PerformanceMetricsMiddleware,
    TraceIdContextMiddleware,
)
from utils.port_utils import get_ip_and_free_port

log = logging.getLogger(__name__)


def create_app_with_configs() -> AduibAIApp:
    def custom_generate_unique_id(route: APIRoute) -> str:
        return f"{route.tags[0]}-{route.name}"

    docs_url = "/docs" if config.SWAGGER_ENABLED else None
    redoc_url = "/redoc" if config.SWAGGER_ENABLED else None
    openapi_url = "/openapi.json" if config.SWAGGER_ENABLED else None
    app = AduibAIApp(
        title=config.APP_NAME,
        generate_unique_id_function=custom_generate_unique_id,
        debug=config.DEBUG,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.config = config
    if config.APP_HOME:
        app.app_home = config.APP_HOME
        app.workdir = config.APP_HOME + "/workdir"
    else:
        app.app_home = os.getenv("USER.HOME", str(pathlib.Path.home())) + f"/.{config.APP_NAME.lower()}"
        app.workdir = app.app_home + "/workdir"
    app.include_router(api_router, prefix="/v1")
    if config.all_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.all_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if config.DEBUG:
        log.warning("Running in debug mode, this is not recommended for production use.")
        app.add_middleware(LoggingMiddleware)
    app.add_middleware(TraceIdContextMiddleware)
    app.add_middleware(ApiKeyContextMiddleware)
    app.add_middleware(PerformanceMetricsMiddleware)
    return app


def create_app() -> AduibAIApp:
    start_time = time.perf_counter()
    app = create_app_with_configs()
    init_logging(app)
    init_apps(app)
    end_time = time.perf_counter()
    log.info("App home directory: %s", app.app_home)
    log.info("Finished create_app (%s ms)", round((end_time - start_time) * 1000, 2))
    return app


def init_apps(app: AduibAIApp):
    """
    Initialize the app with necessary configurations and middlewares.
    :param app: AduibAIApp instance
    """
    log.info("Initializing middlewares")
    init_cache(app)
    init_storage(app)
    from event.event_manager import EventManager, event_manager_context

    event_manager = EventManager()
    app.extensions["event_manager"] = event_manager
    event_manager_context.set(event_manager)
    from component.clickhouse.client import init_clickhouse

    init_clickhouse(app)

    log.info("middlewares initialized successfully")


async def run_service_register(app: AduibAIApp):
    """
    Start RPC service registration and server.
    This function implements singleton pattern to ensure RPC service only starts once.
    """
    log.info("Starting RPC service registration...")
    try:
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
        from aduib_rpc.discover.entities import ServiceInstance
        from aduib_rpc.discover.registry.registry_factory import ServiceRegistryFactory
        from aduib_rpc.discover.service import AduibServiceFactory
        from aduib_rpc.server.rpc_execution.service_call import load_service_plugins
        from aduib_rpc.utils.constant import AIProtocols, TransportSchemes

        # Get IP and determine RPC port
        preferred_port = config.RPC_SERVICE_PORT if config.RPC_SERVICE_PORT > 0 else None
        ip, port = get_ip_and_free_port(preferred_port=preferred_port)

        log.info("RPC service will use IP: %s, Port: %s", ip, port)

        service_registry = ServiceRegistryFactory.start_service_discovery(registry_config)
        rpc_service_info = ServiceInstance(
            service_name=registry_config.get("APP_NAME", "aduib-rpc"),
            host=ip,
            port=port,
            protocol=AIProtocols.AduibRpc,
            weight=1,
            scheme=config.SERVICE_TRANSPORT_SCHEME or TransportSchemes.GRPC,
        )

        factory = AduibServiceFactory(service_instance=rpc_service_info)
        load_service_plugins("rpc.service")
        load_service_plugins("rpc.client")

        # Docker environment configuration
        if config.DOCKER_ENV:
            rpc_service_info = ServiceInstance(
                service_name=rpc_service_info.service_name,
                host=config.RPC_SERVICE_HOST,
                port=rpc_service_info.port,
                protocol=rpc_service_info.protocol,
                weight=rpc_service_info.weight,
                scheme=rpc_service_info.scheme,
            )

        # Setup AI app service instance
        aduib_ai_service = rpc_service_info.__deepcopy__()
        aduib_ai_service.service_name = config.APP_NAME + "-app"
        if config.DOCKER_ENV:
            aduib_ai_service.host = config.RPC_SERVICE_HOST
            aduib_ai_service.port = config.APP_PORT
        else:
            aduib_ai_service.host = config.RPC_SERVICE_HOST
            aduib_ai_service.port = port

        # Register services
        await service_registry.register_service(rpc_service_info)
        log.info(
            "Registered RPC service: %s at %s:%s",
            rpc_service_info.service_name,
            rpc_service_info.host,
            rpc_service_info.port,
        )

        await service_registry.register_service(aduib_ai_service)
        log.info(
            "Registered AI app service: %s at %s:%s",
            aduib_ai_service.service_name,
            aduib_ai_service.host,
            aduib_ai_service.port,
        )

        # Run RPC server
        await factory.run_server()

    except Exception as e:
        log.exception("Failed to start RPC service")
        _rpc_service_started = False
        raise


@contextlib.asynccontextmanager
async def lifespan(app: AduibAIApp) -> AsyncIterator[None]:
    """
    Application lifespan manager - handles startup and shutdown logic.
    """
    log.info("Lifespan is starting")

    from libs.context import app_context

    with app_context.temporary_set(app):
        asyncio.create_task(run_service_register(app))

        from event.event_manager import EventManager

        event_manager: EventManager = app.extensions.get("event_manager")
        if event_manager:
            event_manager.start()
            log.info("Event manager started")

        try:
            from runtime.memory.task_queue import MemoryWriteTaskQueueRuntime

            await MemoryWriteTaskQueueRuntime.start(app)
        except Exception:
            log.exception("Failed to initialize memory write task queue")

        # Ensure default admin account exists
        try:
            from service.user_service import UserService

            UserService.ensure_admin_exists()
        except Exception as e:
            log.exception("Failed to ensure admin account")

        # Register builtin agents and initialize OrchestrationManager
        try:

            from runtime.agent.builtin_agents import register_builtin_agents
            from runtime.tasks.cron_scheduler import cron_scheduler

            register_builtin_agents()
            cron_scheduler.start()
        except Exception as e:
            log.exception("Failed to register builtin agents/workflows")

        try:
            from runtime.agent_manager import AgentManager

            app.agent_manager = AgentManager("supervisor_agent_v3")
            log.info("AgentManager initialized")
        except Exception as e:
            log.exception("Failed to initialize AgentManager")

        yield None

        # Shutdown logic
        log.info("Application is shutting down, cleaning up resources...")

        # Stop event manager
        if event_manager:
            try:
                await event_manager.stop()
                log.info("Event manager stopped")
            except Exception as e:
                log.exception("Error stopping event manager")

        try:
            from runtime.tasks.cron_scheduler import cron_scheduler

            cron_scheduler.stop()
        except Exception as e:
            log.exception("Error stopping cron scheduler")

        try:
            from runtime.memory.task_queue import MemoryWriteTaskQueueRuntime

            await MemoryWriteTaskQueueRuntime.stop(app)
        except Exception:
            log.exception("Error stopping memory write task queue")

        # Close database connections
        try:
            from models.engine import engine

            engine.dispose()
            log.info("Database connections closed")
        except Exception as e:
            log.exception("Error closing database connections")
        log.info("Application shutdown complete")
