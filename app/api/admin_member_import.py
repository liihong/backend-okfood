"""管理端：会员批量导入（模板下载、预览、确认入库）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.core.limiter import limiter
from app.schemas.member_import import MemberImportConfirmIn, MemberImportConfirmResultOut, MemberImportPreviewOut
from app.services.admin.member_import_service import build_member_import_preview, confirm_member_import
from app.services.admin.member_import_xlsx import build_member_import_template_xlsx
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin/members/import", tags=["管理端-会员导入"])

# 上传文件大小上限（5MB，足够数千行会员数据）
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get("/template.xlsx", response_model=None)
def member_import_template_xlsx(
    admin_username: str = Depends(admin_staff_subject),
):
    """下载会员批量导入 Excel 模板（含填写说明与示例行）。"""
    _ = admin_username
    try:
        body = build_member_import_template_xlsx()
    except ImportError:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="导出 Excel 需要 openpyxl，请在服务器虚拟环境中执行：pip install -r requirements.txt",
        ) from None
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="member_import_template.xlsx"'},
    )


@router.post("/preview")
@limiter.limit("30/minute")
async def member_import_preview(
    request: Request,
    db: SessionDep,
    file: UploadFile = File(..., description="填写完成的会员导入 xlsx"),
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """上传 Excel 并返回预览：行级校验、重复手机号跳过提示。"""
    _ = request
    tenant_id, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        from app.utils.response import fail

        return fail(msg=f"文件过大，请控制在 {_MAX_UPLOAD_BYTES // 1024 // 1024}MB 以内")
    if not raw:
        from app.utils.response import fail

        return fail(msg="上传文件为空")
    preview = build_member_import_preview(
        db,
        file_bytes=raw,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
    )
    return success(data=dump_model(preview), msg="解析成功")


@router.post("/confirm")
@limiter.limit("10/minute")
def member_import_confirm(
    request: Request,
    db: SessionDep,
    body: MemberImportConfirmIn,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """确认入库：将预览中可入库的会员写入当前租户门店。"""
    _ = request
    tenant_id, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    if not body.rows:
        from app.utils.response import fail

        return fail(msg="没有可入库的数据")
    result = confirm_member_import(
        db,
        body=body,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        operator=admin_username,
    )
    return success(data=dump_model(result), msg="入库完成")
