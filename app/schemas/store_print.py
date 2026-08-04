"""门店打印：Schema 与常量。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

PrintBrand = Literal["local_label", "xprinter_cloud_label", "feie_label", "yilian_k4"]
PrintScene = Literal["delivery_sheet", "store_retail"]
CopiesMode = Literal["per_unit", "per_order"]
LabelOrderKind = Literal["", "delivery", "retail", "mall"]

PRINT_SCENES: tuple[str, ...] = ("delivery_sheet", "store_retail")

PRINT_BRANDS: dict[str, str] = {
    "local_label": "本地标签机",
    "xprinter_cloud_label": "芯烨云标签",
    "feie_label": "飞鹅标签 FP-N20W",
    "yilian_k4": "易联云 K4",
}

CLOUD_PRINT_BRANDS: frozenset[str] = frozenset({"xprinter_cloud_label", "feie_label", "yilian_k4"})

PAPER_PRESETS: dict[str, tuple[int, int]] = {
    "76x130": (76, 130),
    "80x60": (80, 60),
    "80x50": (80, 50),
    "100x80": (100, 80),
    "100x150": (100, 150),
    "100x180": (100, 180),
    "40x30": (40, 30),
}

PRINT_TEMPLATES: list[dict[str, Any]] = [
    {
        "key": "delivery_meal_full",
        "scene": "delivery_sheet",
        "name": "备餐面单（推荐）",
        "description": "顺丰同城风格 76×130：门店名、顺丰条码、订单号/片区/会员/餐别/备注/tips",
    },
    {
        "key": "delivery_standard",
        "scene": "delivery_sheet",
        "name": "标准备餐标签",
        "description": "顶部大字片区，地址、姓名、份数、备注、业务日",
    },
    {
        "key": "delivery_compact",
        "scene": "delivery_sheet",
        "name": "紧凑标签",
        "description": "适合 80×60mm，字段合并",
    },
    {
        "key": "delivery_large_region",
        "scene": "delivery_sheet",
        "name": "大字片区",
        "description": "片区突出，便于分拣",
    },
    {
        "key": "delivery_meal_full",
        "scene": "store_retail",
        "name": "备餐面单（推荐）",
        "description": "与配送标签同款 76×130：订单号/片区/会员/餐品/备注/tips",
    },
    {
        "key": "retail_delivery",
        "scene": "store_retail",
        "name": "商城配送标签（旧）",
        "description": "配送到家：片区、地址、商品、数量",
    },
    {
        "key": "retail_pickup",
        "scene": "store_retail",
        "name": "商城自提标签",
        "description": "门店自提：姓名、商品、取货日",
    },
    {
        "key": "retail_simple",
        "scene": "store_retail",
        "name": "简洁商品标签",
        "description": "商品名 + 数量 + 联系人",
    },
]

DEFAULT_SCENE_TEMPLATE: dict[str, str] = {
    "delivery_sheet": "delivery_meal_full",
    "store_retail": "delivery_meal_full",
}


# 备餐面单模板底部固定提示
DELIVERY_MEAL_FULL_TIPS = "1.若暂不吃，优先建议冷藏保存！"


class LabelItemIn(BaseModel):
    """单张标签业务字段（前后端共用结构）。"""

    region: str = Field("", description="所属片区")
    address: str = Field("", description="详细地址")
    name: str = Field("", description="收货人")
    phone_tail: str = Field("", description="手机尾号")
    phone_masked: str = Field("", description="脱敏手机号，如 132****6633")
    plan_type: str = Field("", description="会员类别：次卡/周卡/月卡")
    store_name: str = Field("", description="门店名称")
    meal_category: str = Field("", description="餐别/卡种类，如 午餐卡、晚餐卡、午晚餐卡")
    units: int = Field(1, ge=1, description="份数")
    remark: str = Field("", description="备注")
    delivery_date: str = Field("", description="配送业务日")
    route_seq: int | None = Field(None, description="线路序号")
    product_title: str = Field("", description="商品名（零售）")
    order_no: str = Field("", description="展示用订单号：大表备餐短号（片区编码+序号）或零售 out_trade_no")
    shop_order_id: str = Field("", description="顺丰商家订单号（推单 shop_order_id）")
    sf_order_id: str = Field("", description="顺丰运单号（条码内容）")
    store_pickup: bool = Field(False, description="是否自提")
    order_kind: LabelOrderKind = Field(
        "",
        description="订单类别：delivery=订阅配送；retail=零售单次；mall=商城零售；空=按订阅配送处理",
    )


class TenantPrintCloudCredentialsOut(BaseModel):
    feie_user: str | None = None
    feie_ukey_set: bool = False
    xprinter_user: str | None = None
    xprinter_user_key_set: bool = False
    yilian_partner: str | None = None
    yilian_apikey_set: bool = False


class TenantPrintCloudCredentialsPatchIn(BaseModel):
    feie_user: str | None = Field(None, max_length=64)
    feie_ukey: str | None = Field(None, max_length=128, description="空串清除")
    xprinter_user: str | None = Field(None, max_length=64)
    xprinter_user_key: str | None = Field(None, max_length=128)
    yilian_partner: str | None = Field(None, max_length=32)
    yilian_apikey: str | None = Field(None, max_length=128)


class StorePrintProfileOut(BaseModel):
    id: int
    store_id: int
    name: str
    brand: str
    brand_label: str = ""
    cloud_sn: str | None = None
    cloud_device_key_set: bool = False
    paper_preset: str
    paper_width_mm: int
    paper_height_mm: int
    local_printer_name_hint: str | None = None
    margin_top_mm: int
    margin_left_mm: int
    is_default: bool
    is_active: bool


class StorePrintProfileCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    brand: PrintBrand
    cloud_sn: str | None = Field(None, max_length=64)
    cloud_device_key: str | None = Field(None, max_length=128)
    paper_preset: str = Field("80x60", max_length=32)
    paper_width_mm: int = Field(80, ge=20, le=200)
    paper_height_mm: int = Field(60, ge=15, le=300)
    local_printer_name_hint: str | None = Field(None, max_length=128)
    margin_top_mm: int = Field(2, ge=0, le=20)
    margin_left_mm: int = Field(2, ge=0, le=20)
    is_default: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def _cloud_fields(self) -> StorePrintProfileCreateIn:
        if self.brand in CLOUD_PRINT_BRANDS:
            sn = (self.cloud_sn or "").strip()
            if not sn:
                raise ValueError("云打印机须填写 SN / 终端号")
            if self.brand == "feie_label" and not (self.cloud_device_key or "").strip():
                raise ValueError("飞鹅标签机须填写 KEY")
            if self.brand == "yilian_k4" and not (self.cloud_device_key or "").strip():
                raise ValueError("易联云 K4 须填写终端密钥 msign")
        return self


class StorePrintProfilePatchIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    cloud_sn: str | None = Field(None, max_length=64)
    cloud_device_key: str | None = Field(None, max_length=128)
    paper_preset: str | None = Field(None, max_length=32)
    paper_width_mm: int | None = Field(None, ge=20, le=200)
    paper_height_mm: int | None = Field(None, ge=15, le=300)
    local_printer_name_hint: str | None = Field(None, max_length=128)
    margin_top_mm: int | None = Field(None, ge=0, le=20)
    margin_left_mm: int | None = Field(None, ge=0, le=20)
    is_default: bool | None = None
    is_active: bool | None = None


class StorePrintSceneSettingOut(BaseModel):
    scene: str
    scene_label: str = ""
    profile_id: int | None = None
    template_key: str
    copies_mode: CopiesMode = "per_unit"


class StorePrintSceneSettingsPutIn(BaseModel):
    settings: list[StorePrintSceneSettingOut]


class StorePrintResolveOut(BaseModel):
    scene: str
    profile_id: int | None
    brand: str | None
    brand_label: str = ""
    template_key: str
    copies_mode: CopiesMode
    paper_width_mm: int | None = None
    paper_height_mm: int | None = None
    local_printer_name_hint: str | None = None
    configured: bool = False


class StorePrintJobCreateIn(BaseModel):
    scene: PrintScene
    items: list[LabelItemIn] = Field(..., min_length=1)
    profile_id: int | None = Field(None, description="指定打印机，默认用场景绑定")
    template_key: str | None = Field(None, description="指定模板，默认用场景绑定")


class StorePrintJobOut(BaseModel):
    job_id: int
    driver: str
    status: str
    printed_count: int = 0
    local_payload: dict[str, Any] | None = None
    error_msg: str | None = None
