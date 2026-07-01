"""配送大表 · 推送及时单（门店零售 shop）"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.delivery.sf_same_city_service import _apply_instant_sf_shop_gset, _instant_sf_shop_configured


def test_instant_sf_shop_configured_requires_retail_shop_id(monkeypatch):
    db = MagicMock()
    st = SimpleNamespace(sf_retail_push_shop_id="6284388701377", sf_retail_push_shop_type=1)
    db.get.return_value = st
    gset = SimpleNamespace(
        SF_OPEN_DEV_ID=1,
        SF_OPEN_SECRET="sec",
        SF_PICKUP_PHONE="13800000000",
        SF_PICKUP_ADDRESS="取件地址",
    )
    monkeypatch.setattr(
        "app.services.delivery.sf_same_city_service.merged_sf_integration_namespace",
        lambda _db, _tid: gset,
    )
    assert _instant_sf_shop_configured(db, store_id=1, tenant_id=1) is True

    st2 = SimpleNamespace(sf_retail_push_shop_id="", sf_retail_push_shop_type=None)
    db.get.return_value = st2
    assert _instant_sf_shop_configured(db, store_id=1, tenant_id=1) is False


def test_apply_instant_sf_shop_gset_overrides_shop():
    gset = SimpleNamespace(SF_OPEN_SHOP_ID="bulk-shop", SF_OPEN_SHOP_TYPE=1)
    st = SimpleNamespace(sf_retail_push_shop_id="instant-shop", sf_retail_push_shop_type=2)
    out = _apply_instant_sf_shop_gset(gset, st)
    assert out is not gset
    assert out.SF_OPEN_SHOP_ID == "instant-shop"
    assert out.SF_OPEN_SHOP_TYPE == 2
    assert gset.SF_OPEN_SHOP_ID == "bulk-shop"


def test_apply_instant_sf_shop_gset_missing_retail_raises():
    gset = SimpleNamespace(SF_OPEN_SHOP_ID="bulk-shop", SF_OPEN_SHOP_TYPE=1)
    st = SimpleNamespace(sf_retail_push_shop_id=None, sf_retail_push_shop_type=None)
    with pytest.raises(ValueError, match="零售推顺丰店铺ID"):
        _apply_instant_sf_shop_gset(gset, st)
