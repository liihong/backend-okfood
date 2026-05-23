"""顺丰推单 error_code=0 表示创单成功，须与 None/失败区分。"""

from types import SimpleNamespace

from app.services.single_meal_order_service import sf_push_create_succeeded, sf_push_is_terminal_cancel
from app.services.sf_order_fulfillment_service import should_apply_sf_cancel_sync, should_run_sf_auto_fulfillment


def _pus(**kwargs):
    defaults = {
        "error_code": 0,
        "sf_callback_order_status": None,
        "last_callback_kind": "",
        "merchant_cancel_requested_at": None,
        "stop_id": "retail-smo-1",
        "push_kind": "single_meal_retail",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_sf_push_create_succeeded_treats_zero_as_success():
    assert sf_push_create_succeeded(_pus(error_code=0)) is True
    assert sf_push_create_succeeded(_pus(error_code=None)) is False
    assert sf_push_create_succeeded(_pus(error_code=1)) is False
    # 旧写法 ``error_code or -1`` 会把 0 误判为 -1
    pus = _pus(error_code=0)
    assert int(pus.error_code or -1) == -1
    assert sf_push_create_succeeded(pus) is True


def test_should_run_auto_fulfillment_when_error_code_zero():
    pus = _pus(error_code=0, sf_callback_order_status=17, last_callback_kind="order_complete")
    assert should_run_sf_auto_fulfillment(route_kind="order_complete", pus=pus) is True


def test_single_meal_fulfillment_allows_dispatch():
    from app.services.single_meal_order_service import single_meal_fulfillment_allows_dispatch

    assert single_meal_fulfillment_allows_dispatch("pending") is True
    assert single_meal_fulfillment_allows_dispatch("sf_cancelled") is True
    assert single_meal_fulfillment_allows_dispatch("accepted") is False
    assert single_meal_fulfillment_allows_dispatch("delivered") is False
    assert single_meal_fulfillment_allows_dispatch("cancelled") is False


def test_should_apply_cancel_sync_when_error_code_zero():
    pus = _pus(error_code=0, sf_callback_order_status=2, last_callback_kind="cancel_by_sf")
    assert should_apply_sf_cancel_sync(pus=pus) is True
    assert sf_push_is_terminal_cancel(pus) is True
