from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class CourierRegionOut(BaseModel):
    region_id: int
    name: str
    is_primary: bool


class CourierAdminOut(BaseModel):
    courier_id: str
    name: str | None
    phone: str | None
    is_active: bool
    fee_pending: Decimal
    fee_settled: Decimal
    regions: list[CourierRegionOut]


class CourierCreateIn(BaseModel):
    courier_id: str = Field(..., min_length=1, max_length=50)
    name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    pin: str = Field(..., min_length=4, max_length=32)
    is_active: bool = True


class CourierUpdateIn(BaseModel):
    name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    is_active: bool | None = None
    fee_pending: Decimal | None = Field(None, ge=0)
    fee_settled: Decimal | None = Field(None, ge=0)


class CourierPinResetIn(BaseModel):
    pin: str = Field(..., min_length=4, max_length=32)
