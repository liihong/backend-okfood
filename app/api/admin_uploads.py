"""管理端：通用图片上传（菜品图等）。"""

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.core.deps import admin_subject
from app.core.limiter import limiter
from app.schemas.admin import FileUploadOut
from app.services.upload_service import save_image_bytes
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin", tags=["管理端"])


@router.post("/upload")
@limiter.limit("60/minute")
async def admin_upload_image(
    request: Request,
    file: UploadFile = File(..., description="图片文件"),
    admin_username: str = Depends(admin_subject),
):
    _ = request
    _ = admin_username
    data = await file.read()
    url = save_image_bytes(data, file.content_type, file.filename)
    return success(data=dump_model(FileUploadOut(url=url)), msg="上传成功")
