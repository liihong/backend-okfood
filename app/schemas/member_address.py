from pydantic import BaseModel, Field

from app.schemas.user import Location


class MemberAddressOut(BaseModel):
    id: int
    member_id: int
    contact_name: str
    contact_phone: str
    delivery_region_id: int | None = None
    area: str = Field(..., description="片区展示名，由 delivery_region_id 解析；未分配为「未分配」")
    detail_address: str
    map_location_text: str | None = Field(None, description="地图选点/省市区道路小区等")
    door_detail: str | None = Field(None, description="楼栋、单元、门牌等")
    remarks: str | None
    location: Location | None
    is_default: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": False}


class MemberAddressCreateIn(BaseModel):
    contact_name: str = Field(..., min_length=1, max_length=100)
    contact_phone: str = Field(..., min_length=5, max_length=20)
    detail_address: str = Field(..., min_length=1, max_length=500)
    map_location_text: str | None = Field(None, max_length=500)
    door_detail: str | None = Field(None, max_length=500)
    remarks: str | None = Field(None, max_length=500)
    is_default: bool = False
    location: Location | None = Field(
        None,
        description="地图选点坐标；若提供则保存该经纬度并据此自动划区，不再对详细地址做地理编码",
    )


class MemberAddressUpdateIn(BaseModel):
    contact_name: str | None = Field(None, min_length=1, max_length=100)
    contact_phone: str | None = Field(None, min_length=5, max_length=20)
    detail_address: str | None = Field(None, min_length=1, max_length=500)
    map_location_text: str | None = Field(None, max_length=500)
    door_detail: str | None = Field(None, max_length=500)
    remarks: str | None = Field(None, max_length=500)
    is_default: bool | None = None
    location: Location | None = Field(
        None,
        description="更新地图选点；提交则刷新经纬度并按坐标重算片区",
    )
