from pydantic import BaseModel, Field

from app.schemas.user import Location


class MemberAddressOut(BaseModel):
    id: int
    member_id: int
    contact_name: str
    contact_phone: str
    delivery_region_id: int | None = None
    area: str = Field(..., description="片区展示名，由 delivery_region_id 解析；未分配为「未分配」")
    map_location_text: str | None = Field(None, description="地图选点/收货位置主文案（可含省市区道路小区等前缀）")
    door_detail: str | None = Field(None, description="楼栋、单元、门牌等")
    full_address: str = Field(
        "",
        description="完整收货地址：map_location_text 与 door_detail 按空格拼接；展示与地理编码一律用此语义",
    )
    remarks: str | None
    location: Location | None
    is_default: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": False}


class MemberAddressCreateIn(BaseModel):
    contact_name: str = Field(..., min_length=1, max_length=100)
    contact_phone: str = Field(..., min_length=5, max_length=20)
    map_location_text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="收货位置主文案；有坐标时服务端逆地理可将省市区前缀规范化并入本字段",
    )
    door_detail: str | None = Field(None, max_length=500)
    remarks: str | None = Field(None, max_length=500)
    is_default: bool = False
    location: Location | None = Field(
        None,
        description="地图选点坐标；若提供则保存该经纬度并据此自动划区，不再对拼接地址做地理编码",
    )


class DeliveryRegionCheckIn(BaseModel):
    location: Location = Field(..., description="地图选点坐标（gcj02）")


class DeliveryRegionCheckOut(BaseModel):
    in_region: bool = Field(..., description="坐标是否落在启用的配送片区内")
    delivery_region_id: int | None = Field(None, description="命中片区 id；未命中为 null")
    region_name: str | None = Field(None, description="命中片区名称；未命中为 null")


class MemberAddressUpdateIn(BaseModel):
    contact_name: str | None = Field(None, min_length=1, max_length=100)
    contact_phone: str | None = Field(None, min_length=5, max_length=20)
    map_location_text: str | None = Field(
        None,
        max_length=500,
        description="收货位置主文案；与坐标一并提交时会按逆地理规范省市区前缀",
    )
    door_detail: str | None = Field(None, max_length=500)
    remarks: str | None = Field(None, max_length=500)
    is_default: bool | None = None
    location: Location | None = Field(
        None,
        description="更新地图选点；提交则刷新经纬度并按坐标重算片区",
    )
