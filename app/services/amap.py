import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# https://lbs.amap.com/api/webservice/guide/tools/info
_GEO_FAIL_HINTS: dict[str, str] = {
    "10005": (
        "请求 IP 不在白名单（INVALID_USER_IP）。请在控制台该 Web 服务 Key 的「安全设置」中"
        "将本机/服务器访问高德时的公网出口 IP 加入白名单，或开发环境暂时关闭 IP 白名单。"
    ),
    "10009": (
        "Key 与接口平台不匹配（USERKEY_PLAT_NOMATCH）。服务端地理编码须使用控制台中"
        "「应用」→ 添加 Key → 服务平台选「Web服务」生成的 Key。"
    ),
}


def _sanitize_amap_payload(data: dict[str, Any]) -> dict[str, Any]:
    drop = {"key", "sec_code", "sec_code_debug"}
    return {k: v for k, v in data.items() if k not in drop}


def geocode_address(address: str) -> tuple[float, float] | None:
    """
    高德地理编码：返回 (lng, lat)，GCJ-02。
    失败返回 None，由上层决定片区与坐标策略。
    """
    key = settings.AMAP_KEY.strip()
    if not key:
        logger.warning("AMAP_KEY 未配置，跳过地理编码")
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"address": address, "key": key},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except Exception as e:
        logger.exception("高德地理编码请求失败: %s", e)
        return None
    if str(data.get("status")) != "1":
        safe = _sanitize_amap_payload(data)
        logger.warning("高德地理编码失败: %s", safe)
        code = str(data.get("infocode") or "")
        hint = _GEO_FAIL_HINTS.get(code)
        if hint:
            logger.warning("处理建议: %s", hint)
        elif (data.get("info") or "") == "USERKEY_PLAT_NOMATCH":
            logger.warning("处理建议: %s", _GEO_FAIL_HINTS["10009"])
        return None
    geos = data.get("geocodes") or []
    if not geos:
        return None
    loc = (geos[0] or {}).get("location") or ""
    parts = str(loc).split(",")
    if len(parts) != 2:
        return None
    try:
        lng, lat = float(parts[0]), float(parts[1])
        return lng, lat
    except ValueError:
        return None


def regeocode_pca(lng: float, lat: float) -> str | None:
    """
    高德逆地理编码：根据 GCJ-02 经纬度解析省/市/区，拼成一条「收货大地址」前缀（不含门牌）。
    失败或未配置 Key 时返回 None。
    """
    key = settings.AMAP_KEY.strip()
    if not key:
        logger.warning("AMAP_KEY 未配置，跳过逆地理编码")
        return None
    loc = f"{float(lng):.6f},{float(lat):.6f}"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                "https://restapi.amap.com/v3/geocode/regeo",
                params={"location": loc, "key": key, "radius": 50, "extensions": "base"},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except Exception as e:
        logger.exception("高德逆地理编码请求失败: %s", e)
        return None
    if str(data.get("status")) != "1":
        safe = _sanitize_amap_payload(data)
        logger.warning("高德逆地理编码失败: %s", safe)
        code = str(data.get("infocode") or "")
        hint = _GEO_FAIL_HINTS.get(code)
        if hint:
            logger.warning("处理建议: %s", hint)
        return None
    regeocode = (data.get("regeocode") or {}) if isinstance(data.get("regeocode"), dict) else {}
    ac = regeocode.get("addressComponent")
    if not isinstance(ac, dict):
        return None
    pca = _format_pca_from_amap_component(ac)
    return pca if pca else None


def _format_pca_from_amap_component(ac: dict[str, Any]) -> str:
    prov = str(ac.get("province") or "").strip()
    city_raw = ac.get("city")
    if isinstance(city_raw, list):
        city = str(city_raw[0]).strip() if city_raw else ""
    else:
        city = str(city_raw or "").strip()
    district = str(ac.get("district") or "").strip()
    parts: list[str] = []
    if prov:
        parts.append(prov)
    if city and city not in prov and all(city not in p for p in parts):
        parts.append(city)
    if district and all(district not in p for p in parts):
        parts.append(district)
    return "".join(parts).strip()
