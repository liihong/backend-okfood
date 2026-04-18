from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.services.region_geo import extract_outer_ring


class RegionCourierAssignIn(BaseModel):
    courier_id: str = Field(..., min_length=1, max_length=50)
    is_primary: bool = False
    sort_order: int = 0


class DeliveryRegionCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str | None = Field(None, max_length=32)
    polygon_json: dict[str, Any] | list[Any]
    priority: int = 0
    is_active: bool = True
    couriers: list[RegionCourierAssignIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_polygon(self) -> DeliveryRegionCreateIn:
        extract_outer_ring(self.polygon_json)
        return self


class DeliveryRegionUpdateIn(BaseModel):
    """PATCH 风格：仅更新提供的字段；`couriers` 若提供则全量替换绑定。"""

    name: str | None = Field(None, min_length=1, max_length=64)
    code: str | None = None
    polygon_json: dict[str, Any] | list[Any] | None = None
    priority: int | None = None
    is_active: bool | None = None
    couriers: list[RegionCourierAssignIn] | None = None

    @model_validator(mode="after")
    def _validate_polygon(self) -> DeliveryRegionUpdateIn:
        if self.polygon_json is not None:
            extract_outer_ring(self.polygon_json)
        return self


class RegionCourierOut(BaseModel):
    courier_id: str
    name: str | None
    is_primary: bool
    sort_order: int


class DeliveryRegionSummaryOut(BaseModel):
    """列表用：不含 polygon，减轻 DB/网络/JSON 体积（多边形仅在详情或编辑时加载）。"""

    id: int
    name: str
    code: str | None
    priority: int
    is_active: bool
    couriers: list[RegionCourierOut]


class DeliveryRegionOut(DeliveryRegionSummaryOut):
    polygon_json: dict[str, Any] | list[Any]


class MapOverviewMemberMarkerOut(BaseModel):
    """地图会员点：默认地址上的展示片区与 GCJ-02 坐标（可空）。"""

    id: int
    name: str
    phone: str
    area: str
    lng: float | None = None
    lat: float | None = None


class DeliveryRegionMapOverviewOut(BaseModel):
    regions: list[DeliveryRegionOut]
    members: list[MapOverviewMemberMarkerOut]
