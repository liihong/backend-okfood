"""存量库幂等补丁：启动时补列，避免新代码读到旧表结构。"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_USAGE_INDEX = "idx_member_addresses_member_usage_default"


def ensure_member_address_usage_schema(engine: Engine) -> None:
    """为 member_addresses 补 address_usage 列（meal/retail），已存在则跳过。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "member_addresses" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("member_addresses")}
    dialect = engine.dialect.name
    if "address_usage" not in cols:
        with engine.begin() as conn:
            if dialect == "sqlite":
                conn.execute(
                    text(
                        "ALTER TABLE member_addresses "
                        "ADD COLUMN address_usage VARCHAR(16) NOT NULL DEFAULT 'meal'"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE `member_addresses` "
                        "ADD COLUMN `address_usage` VARCHAR(16) NOT NULL DEFAULT 'meal' "
                        "COMMENT 'meal=会员送餐地址；retail=果蔬汁/月饼等商城收货地址' "
                        "AFTER `is_default`"
                    )
                )
        logger.info("已为 member_addresses 补 address_usage 列")

    if dialect == "sqlite":
        return
    insp = inspect(engine)
    idx_names = {i["name"] for i in insp.get_indexes("member_addresses")}
    if _USAGE_INDEX in idx_names:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE `member_addresses` "
                f"ADD INDEX `{_USAGE_INDEX}` "
                "(`member_id`, `address_usage`, `is_default`)"
            )
        )
    logger.info("已为 member_addresses 补 address_usage 索引")


def apply_address_usage_data_backfill(db: Session) -> None:
    """把无餐次用户的地址标为零售，并把商城订单从餐次地址上解绑（复制后改绑）。"""
    from app.services.member.member_address_service import backfill_retail_address_separation

    backfill_retail_address_separation(db)
