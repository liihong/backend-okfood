"""会员批量导入：模板下载、预览与确认入库的请求/响应模型。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import PlanType

# 预览行状态：ready 可入库；error 校验失败；skip 跳过（如手机号已存在）
MemberImportRowStatus = Literal["ready", "error", "skip"]


class MemberImportRowData(BaseModel):
    """单条待入库会员的标准化数据（预览与确认共用）。"""

    phone: str = Field(..., min_length=5, max_length=20, description="手机号")
    name: str = Field(..., min_length=1, max_length=100, description="会员姓名")
    plan_type: PlanType = Field(..., description="套餐类型：周卡 / 月卡")
    address: str = Field(..., max_length=500, description="配送地址；自提时可填「自提」")
    balance: int = Field(..., ge=0, description="剩余次数")
    meal_quota_total: int = Field(..., ge=0, description="套餐总次数")
    daily_meal_units: int = Field(1, ge=1, le=50, description="每配送日份数")
    delivery_start_date: date | None = Field(None, description="起送业务日")
    store_pickup: bool = Field(False, description="是否门店自提")
    delivery_deferred: bool = Field(False, description="是否暂停配送（暂不进入配送大表）")
    remarks: str | None = Field(None, max_length=500, description="备注")


class MemberImportPreviewRowOut(BaseModel):
    """预览表格中的一行。"""

    row_no: int = Field(..., ge=1, description="Excel 中的行号（含表头从 1 起算）")
    status: MemberImportRowStatus
    messages: list[str] = Field(default_factory=list, description="错误或跳过原因")
    data: MemberImportRowData | None = Field(None, description="校验通过时有值")


class MemberImportPreviewSummaryOut(BaseModel):
    """预览汇总统计。"""

    total: int = Field(..., ge=0, description="有效数据行数（不含空行）")
    ready: int = Field(..., ge=0, description="可入库行数")
    error: int = Field(..., ge=0, description="校验失败行数")
    skip: int = Field(..., ge=0, description="跳过行数（如手机号已存在）")


class MemberImportPreviewOut(BaseModel):
    """上传文件解析后的预览结果。"""

    summary: MemberImportPreviewSummaryOut
    rows: list[MemberImportPreviewRowOut]


class MemberImportConfirmIn(BaseModel):
    """确认入库：前端将预览中 status=ready 的 data 回传，服务端再次校验后写入。"""

    rows: list[MemberImportRowData] = Field(..., min_length=1, description="待入库会员列表")


class MemberImportConfirmResultOut(BaseModel):
    """入库结果。"""

    inserted: int = Field(..., ge=0, description="成功新建会员数")
    skipped: int = Field(..., ge=0, description="因手机号已存在等原因跳过数")
    failed: int = Field(..., ge=0, description="写入失败数")
    messages: list[str] = Field(default_factory=list, description="失败或跳过的明细说明")
