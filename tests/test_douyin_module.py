"""抖音团购模块单元测试。"""

from __future__ import annotations

from app.integrations.douyin_life import DouyinPrepareCertificate
from app.services.douyin.certificate_service import _mask_code
from app.services.douyin.product_mapping_service import _cert_id_set


def test_mask_code():
    assert _mask_code("ab") == "****"
    assert _mask_code("12345678").endswith("5678")


def test_cert_id_set_collects_sku_fields():
    cert = DouyinPrepareCertificate(
        certificate_id="1",
        encrypted_code="enc",
        code="plain",
        product_id="p1",
        sku_id="s1",
        product_out_id="out1",
        sku_out_id=None,
        third_sku_id="t1",
        title="title",
        pay_amount_fen=None,
    )
    ids = _cert_id_set(cert)
    assert ids == {"p1", "s1", "out1", "t1"}
