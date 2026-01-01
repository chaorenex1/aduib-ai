import asyncio
import copy
import logging
from typing import Any, Dict, Optional, Tuple

from configs import config
from utils.port_utils import get_ip_and_free_port

log = logging.getLogger(__name__)


def _build_registry_config() -> Dict[str, Any]:
    """Build discovery/registry configuration from `configs.config`."""
    return {
        "server_addresses": config.NACOS_SERVER_ADDR,
        "namespace": config.NACOS_NAMESPACE,
        "group_name": config.NACOS_GROUP,
        "username": config.NACOS_USERNAME,
        "password": config.NACOS_PASSWORD,
        "DISCOVERY_SERVICE_ENABLED": config.DISCOVERY_SERVICE_ENABLED,
        "DISCOVERY_SERVICE_TYPE": config.DISCOVERY_SERVICE_TYPE,
        "SERVICE_TRANSPORT_SCHEME": config.SERVICE_TRANSPORT_SCHEME,
        "APP_NAME": config.APP_NAME,
    }


def _select_ip_and_port() -> Tuple[str, int]:
    preferred_port: Optional[int] = config.RPC_SERVICE_PORT if config.RPC_SERVICE_PORT and config.RPC_SERVICE_PORT > 0 else None
    return get_ip_and_free_port(preferred_port=preferred_port)


async def run_service_register() -> None:
    """Start RPC service discovery registration and run the RPC server."""
    from app_factory import create_app

    # Ensure app components/config are initialized.
    create_app()

    log.info("Starting RPC service registration...")

    registry_config = _build_registry_config()
    try:
        from aduib_rpc.discover.entities import ServiceInstance
        from aduib_rpc.discover.registry.registry_factory import ServiceRegistryFactory
        from aduib_rpc.discover.service import AduibServiceFactory
        from aduib_rpc.server.rpc_execution.service_call import load_service_plugins
        from aduib_rpc.utils.constant import AIProtocols, TransportSchemes

        ip, port = _select_ip_and_port()
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

        # Load RPC plugins once before starting the server.
        load_service_plugins("rpc.service")
        load_service_plugins("rpc.client")

        # In Docker we often need to advertise container/ingress host to discovery.
        if config.DOCKER_ENV:
            rpc_service_info = ServiceInstance(
                service_name=rpc_service_info.service_name,
                host=config.RPC_SERVICE_HOST,
                port=rpc_service_info.port,
                protocol=rpc_service_info.protocol,
                weight=rpc_service_info.weight,
                scheme=rpc_service_info.scheme,
            )

        # Setup AI app service instance.
        # NOTE: Use a real deepcopy to avoid relying on aduib_rpc's internal API.
        aduib_ai_service = copy.deepcopy(rpc_service_info)
        aduib_ai_service.service_name = f"{config.APP_NAME}-app"

        if config.DOCKER_ENV:
            # App is exposed via a separate HTTP port in docker.
            aduib_ai_service.host = config.RPC_SERVICE_HOST
            aduib_ai_service.port = config.APP_PORT
        else:
            # Non-docker: advertise the same host and chosen port by default.
            # If you want the app to advertise a different port, set DOCKER_ENV+APP_PORT.
            aduib_ai_service.host = rpc_service_info.host
            aduib_ai_service.port = rpc_service_info.port

        # Register services.
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

        # Run RPC server.
        await factory.run_server()

    except Exception:
        # Keep traceback. don't reference undefined state flags.
        log.exception("Failed to start RPC service")
        raise


if __name__ == "__main__":
    asyncio.run(run_service_register())