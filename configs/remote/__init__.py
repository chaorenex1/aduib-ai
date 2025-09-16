from pydantic import Field
from pydantic_settings import BaseSettings

from .base import RemoteSettingsSource
from .enums import RemoteSettingsSourceName
from .nacos import NacosConfig


class RemoteSettingsSourceConfig(NacosConfig):
    REMOTE_SETTINGS_SOURCE_NAME: str = Field(
        description="name of remote config source",
        default="nacos",
    )


class DiscoveryConfig(BaseSettings):
    DISCOVERY_SERVICE_ENABLED: bool = Field(default=False, description="Enable service discovery")
    DISCOVERY_SERVICE_TYPE: str = Field(default="nacos", description="Type of service discovery")
    SERVICE_TRANSPORT_SCHEME: str = Field(default="grpc", description="Service transport scheme, e.g., http or https")




__all__ = ["RemoteSettingsSource", "RemoteSettingsSourceConfig", "RemoteSettingsSourceName", "DiscoveryConfig"]