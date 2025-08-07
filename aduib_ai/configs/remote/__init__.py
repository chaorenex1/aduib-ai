from typing import Union

from pydantic import Field

from .base import RemoteSettingsSource
from .enums import RemoteSettingsSourceName
from .nacos import NacosConfig


class RemoteSettingsSourceConfig(NacosConfig):
    REMOTE_SETTINGS_SOURCE_NAME: str = Field(
        description="name of remote config source",
        default="nacos",
    )


__all__ = ["RemoteSettingsSource", "RemoteSettingsSourceConfig", "RemoteSettingsSourceName"]