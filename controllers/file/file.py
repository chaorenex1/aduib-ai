from fastapi import APIRouter, File, UploadFile
from starlette.responses import StreamingResponse

from controllers.common.base import api_endpoint
from service import FileService

router = APIRouter(tags=["file_upload"])
UPLOAD_FILE = File(...)


@router.post("/upload/bytes")
@api_endpoint()
async def upload_bytes(file: UploadFile = UPLOAD_FILE):
    """通过字节流上传文件"""
    file_record = FileService.upload_bytes(file.filename, await file.read())
    return file_record.access_url


@router.get("/download/{filename}")
@api_endpoint()
async def download_file(filename: str):
    """下载文件（字节流）"""

    def iterfile():
        with FileService.download_file(filename, stream=True) as file:
            yield from file

    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
