import logging
from abc import ABC, abstractmethod
from typing import Generator, Callable, Any, Union

from aduib_app import AduibAIApp
from configs import config

log = logging.getLogger(__name__)


class BaseStorage(ABC):
    @abstractmethod
    def save(self, filename: str, data: Any):
        raise NotImplementedError()

    @abstractmethod
    def load(self, filename: str) -> bytes:
        raise NotImplementedError()

    @abstractmethod
    def load_stream(self, filename: str) -> Generator:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, filename: str):
        raise NotImplementedError()

    @abstractmethod
    def exists(self, filename: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def download(self, filename: str, target_file_path: str):
        raise NotImplementedError()

    @abstractmethod
    def size(self, filename: str) -> int:
        raise NotImplementedError()


class StorageManager:
    def __init__(self):
        self.storage_instance = None

    def init_storage(self, app: AduibAIApp):
        storage = self.get_storage_instance(config.STORAGE_TYPE, app)
        self.storage_instance = storage()

    @staticmethod
    def get_storage_instance(storage_type: str, app: AduibAIApp) -> Callable[[], BaseStorage]:
        match storage_type:
            case "local":
                from .opendal_storage import OpenDALStorage

                storage_path = (
                    config.STORAGE_LOCAL_PATH if config.STORAGE_LOCAL_PATH else app.app_home + "/" + storage_type
                )
                return lambda: OpenDALStorage(scheme="fs", root=storage_path)
            case "s3":
                from .s3_storage import S3Storage

                return S3Storage
            case _:
                raise ValueError(f"Unsupported storage type: {storage_type}")

    def save(self, filename: str, data: Any):
        try:
            self.storage_instance.save(filename, data)
        except Exception as e:
            log.exception(f"Failed to save file {filename}")
            raise e

    def load(self, filename: str, stream: bool) -> Union[bytes, Generator]:
        try:
            if stream:
                return self.storage_instance.load_stream(filename)
            else:
                return self.storage_instance.load(filename)
        except Exception as e:
            log.exception(f"Failed to load file {filename}")
            raise e

    def delete(self, filename: str):
        try:
            self.storage_instance.delete(filename)
        except Exception as e:
            log.exception(f"Failed to delete file {filename}")
            raise e

    def exists(self, filename: str) -> bool:
        try:
            return self.storage_instance.exists(filename)
        except Exception as e:
            log.exception(f"Failed to check file existence {filename}")
            raise e

    def download(self, filename: str, target_file_path: str):
        try:
            self.storage_instance.download(filename, target_file_path)
        except Exception as e:
            log.exception(f"Failed to download file {filename}")
            raise e

    def size(self, filename: str) -> int:
        try:
            return self.storage_instance.size(filename)
        except Exception as e:
            log.exception(f"Failed to get file size {filename}")
            raise e


storage_manager = StorageManager()


def init_storage(app: AduibAIApp):
    storage_manager.init_storage(app)
    app.extensions["storage_manager"] = storage_manager
