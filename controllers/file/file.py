from fastapi import APIRouter, UploadFile, File
from starlette.responses import StreamingResponse

from controllers.common.base import catch_exceptions, BaseResponse
from service import FileService

router = APIRouter(tags=["file_upload"])


@router.post("/upload/bytes")
@catch_exceptions
async def upload_bytes(file: UploadFile = File(...)):
    """通过字节流上传文件"""
    file_record = FileService.upload_bytes(file.filename, await file.read())
    return BaseResponse.ok(file_record.access_url)


@router.get("/download/{filename}")
@catch_exceptions
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
