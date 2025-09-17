import base64
import hashlib
import os
from configs import config

from component.storage.base_storage import storage_manager
from models import get_db, FileResource


class FileService:
    """文件服务"""

    @classmethod
    def upload_bytes(cls, file_name: str, content: bytes):
        """通过字节流上传文件"""
        if content is None or len(content) == 0:
            raise ValueError("Content is empty")
        file_hash = hashlib.sha256(content).hexdigest()
        with get_db() as session:
            existing_file = session.query(FileResource).filter_by(file_hash=file_hash).first()
            if existing_file:
                return existing_file
            else:
                file_type = os.path.splitext(file_name)[1]
                file_path = file_name
                access_url = os.path.join(config.SERVICE_URL, file_name)
                storage_manager.save(file_name, content)
                file_size = len(content)
                file_record = FileResource(
                    file_name=file_name,
                    file_type=file_type,
                    file_path=file_path,
                    access_url=access_url,
                    file_hash=file_hash,
                    file_size=file_size,
                )
                session.add(file_record)
                session.commit()
                return file_record

    @classmethod
    def upload_base64(cls, file_name: str, content: str):
        """通过 base64 上传文件"""
        if content is None or len(content.strip()) == 0:
            raise ValueError("Content is empty")
        content = base64.b64decode(content)
        cls.upload_bytes(file_name, content)

    @classmethod
    def download_file(cls, file_hash: str, stream: bool = False):
        """下载文件（字节流）"""
        if file_hash is None or len(file_hash.strip()) == 0:
            raise ValueError("file_hash is empty")
        with get_db() as session:
            file_record = session.query(FileResource).filter_by(file_hash=file_hash).first()
            if not file_record:
                return None
            content = storage_manager.load(file_record.access_url, stream)
            if not stream:
                file_hash = hashlib.sha256(content).hexdigest()
                if file_hash != file_record.file_hash:
                    raise ValueError("File hash mismatch, file may be corrupted")
            return content

    @classmethod
    def delete_file(cls, file_hash: str):
        """删除文件"""
        if file_hash is None or len(file_hash.strip()) == 0:
            raise ValueError("file_hash is empty")
        with get_db() as session:
            file_record = session.query(FileResource).filter_by(file_hash=file_hash).first()
            if not file_record:
                return False
            storage_manager.delete(file_record.access_url)
            session.delete(file_record)
            session.commit()
            return True
