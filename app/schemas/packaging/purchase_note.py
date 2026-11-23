"""采购资料入参。字段只描述这条备忘本身。"""

from pydantic import BaseModel, Field


class PurchaseNoteIn(BaseModel):
    category: str = Field(..., max_length=16)
    name: str = Field(..., max_length=64)
    record_method: str = Field(..., max_length=16)
    contact_value: str = Field(..., max_length=500)
    platform: str | None = Field(None, max_length=32)
    supplier_label: str | None = Field(None, max_length=64)
    remark: str | None = Field(None, max_length=500)


class PurchaseNotePatchIn(BaseModel):
    category: str | None = Field(None, max_length=16)
    name: str | None = Field(None, max_length=64)
    record_method: str | None = Field(None, max_length=16)
    contact_value: str | None = Field(None, max_length=500)
    platform: str | None = Field(None, max_length=32)
    supplier_label: str | None = Field(None, max_length=64)
    remark: str | None = Field(None, max_length=500)
