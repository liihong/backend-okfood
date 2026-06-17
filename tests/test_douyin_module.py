"""抖音团购模块单元测试。"""

from __future__ import annotations

from decimal import Decimal

from app.integrations.douyin_life import DouyinPrepareCertificate, _parse_prepare_certificates
from app.services.douyin.certificate_service import _amount_from_cert_fen, _mask_code
from app.services.douyin.product_mapping_service import _cert_id_set


def test_mask_code():
    assert _mask_code("ab") == "****"
    assert _mask_code("12345678").endswith("5678")


def test_parse_prepare_certificates_pay_amount_in_fen():
    """抖音 prepare 的 pay_amount 单位为分，解析后应原样存入 pay_amount_fen。"""
    certs = _parse_prepare_certificates(
        {
            "certificates_v2": [
                {
                    "certificate_id": "cid-180",
                    "encrypted_code": "enc-180",
                    "amount": {"pay_amount": 18000},
                }
            ]
        }
    )
    assert len(certs) == 1
    assert certs[0].pay_amount_fen == 18000
    assert _amount_from_cert_fen(certs[0].pay_amount_fen) == Decimal("180.00")


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
