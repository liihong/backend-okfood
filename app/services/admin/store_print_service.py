"""门店打印：CRUD、场景绑定、打印任务分发。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store_print_job import StorePrintJob
from app.models.store_print_profile import StorePrintProfile
from app.models.store_print_scene_setting import StorePrintSceneSetting
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.schemas.store_print import (
    CLOUD_PRINT_BRANDS,
    DEFAULT_SCENE_TEMPLATE,
    PRINT_BRANDS,
    PRINT_SCENES,
    PRINT_TEMPLATES,
    LabelItemIn,
    StorePrintJobCreateIn,
    StorePrintJobOut,
    StorePrintProfileCreateIn,
    StorePrintProfileOut,
    StorePrintProfilePatchIn,
    StorePrintResolveOut,
    StorePrintSceneSettingOut,
    TenantPrintCloudCredentialsOut,
    TenantPrintCloudCredentialsPatchIn,
)
from app.services.print.cloud import feie_client, xprinter_client, yilian_client
from app.services.print.label_renderer import (
    lodop_layout_to_dict,
    render_label_payload,
    render_test_label,
)

logger = logging.getLogger(__name__)

SCENE_LABELS = {"delivery_sheet": "配送大表", "store_retail": "商城零售"}


@dataclass(frozen=True)
class _CloudCreds:
    feie_user: str
    feie_ukey: str
    xprinter_user: str
    xprinter_user_key: str
    yilian_partner: str
    yilian_apikey: str


def _s(v: str | None) -> str:
    return (v or "").strip()


def _profile_out(row: StorePrintProfile) -> StorePrintProfileOut:
    return StorePrintProfileOut(
        id=int(row.id),
        store_id=int(row.store_id),
        name=row.name,
        brand=row.brand,
        brand_label=PRINT_BRANDS.get(row.brand, row.brand),
        cloud_sn=row.cloud_sn,
        cloud_device_key_set=bool(_s(row.cloud_device_key)),
        paper_preset=row.paper_preset,
        paper_width_mm=int(row.paper_width_mm),
        paper_height_mm=int(row.paper_height_mm),
        local_printer_name_hint=row.local_printer_name_hint,
        margin_top_mm=int(row.margin_top_mm),
        margin_left_mm=int(row.margin_left_mm),
        is_default=bool(row.is_default),
        is_active=bool(row.is_active),
    )


def _get_or_create_integration(db: Session, tenant_id: int) -> TenantIntegrationSettings:
    row = db.get(TenantIntegrationSettings, int(tenant_id))
    if row is None:
        row = TenantIntegrationSettings(tenant_id=int(tenant_id))
        db.add(row)
        db.flush()
    return row


def get_tenant_print_cloud_credentials_out(db: Session, tenant_id: int) -> TenantPrintCloudCredentialsOut:
    row = db.get(TenantIntegrationSettings, int(tenant_id))
    if row is None:
        return TenantPrintCloudCredentialsOut()
    return TenantPrintCloudCredentialsOut(
        feie_user=row.feie_user,
        feie_ukey_set=bool(_s(row.feie_ukey)),
        xprinter_user=row.xprinter_user,
        xprinter_user_key_set=bool(_s(row.xprinter_user_key)),
        yilian_partner=row.yilian_partner,
        yilian_apikey_set=bool(_s(row.yilian_apikey)),
    )


def patch_tenant_print_cloud_credentials(
    db: Session, tenant_id: int, body: TenantPrintCloudCredentialsPatchIn
) -> TenantPrintCloudCredentialsOut:
    row = _get_or_create_integration(db, tenant_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None and isinstance(v, str) and v.strip() == "" and k in (
            "feie_ukey",
            "xprinter_user_key",
            "yilian_apikey",
        ):
            setattr(row, k, None)
        elif v is not None:
            setattr(row, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    db.refresh(row)
    return get_tenant_print_cloud_credentials_out(db, tenant_id)


def _load_cloud_creds(db: Session, tenant_id: int, brand: str) -> _CloudCreds:
    row = db.get(TenantIntegrationSettings, int(tenant_id))
    if row is None:
        raise HTTPException(status_code=400, detail="请先在打印机管理配置云打印开发者凭证")
    creds = _CloudCreds(
        feie_user=_s(row.feie_user),
        feie_ukey=_s(row.feie_ukey),
        xprinter_user=_s(row.xprinter_user),
        xprinter_user_key=_s(row.xprinter_user_key),
        yilian_partner=_s(row.yilian_partner),
        yilian_apikey=_s(row.yilian_apikey),
    )
    if brand == "feie_label" and (not creds.feie_user or not creds.feie_ukey):
        raise HTTPException(status_code=400, detail="请配置飞鹅云 USER 与 UKEY")
    if brand == "xprinter_cloud_label" and (not creds.xprinter_user or not creds.xprinter_user_key):
        raise HTTPException(status_code=400, detail="请配置芯烨云开发者账号与 UserKEY")
    if brand == "yilian_k4" and (not creds.yilian_partner or not creds.yilian_apikey):
        raise HTTPException(status_code=400, detail="请配置易联云 partner 与 apikey")
    return creds


def _register_cloud_printer(db: Session, tenant_id: int, profile: StorePrintProfile) -> None:
    creds = _load_cloud_creds(db, tenant_id, profile.brand)
    sn = _s(profile.cloud_sn)
    try:
        if profile.brand == "feie_label":
            feie_client.add_printer(creds.feie_user, creds.feie_ukey, sn, _s(profile.cloud_device_key), profile.name)
        elif profile.brand == "xprinter_cloud_label":
            xprinter_client.add_printer(creds.xprinter_user, creds.xprinter_user_key, sn, profile.name)
        elif profile.brand == "yilian_k4":
            yilian_client.add_terminal(creds.yilian_partner, creds.yilian_apikey, sn, _s(profile.cloud_device_key))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"云打印机绑定失败：{e}") from e


def _clear_other_defaults(db: Session, store_id: int, except_id: int | None = None) -> None:
    q = select(StorePrintProfile).where(
        StorePrintProfile.store_id == int(store_id), StorePrintProfile.is_default.is_(True)
    )
    if except_id is not None:
        q = q.where(StorePrintProfile.id != int(except_id))
    for row in db.scalars(q):
        row.is_default = False


def list_store_print_profiles(db: Session, *, store_id: int) -> list[StorePrintProfileOut]:
    rows = db.scalars(
        select(StorePrintProfile)
        .where(StorePrintProfile.store_id == int(store_id), StorePrintProfile.is_active.is_(True))
        .order_by(StorePrintProfile.is_default.desc(), StorePrintProfile.id.asc())
    ).all()
    return [_profile_out(r) for r in rows]


def create_store_print_profile(
    db: Session, *, tenant_id: int, store_id: int, body: StorePrintProfileCreateIn
) -> StorePrintProfileOut:
    if body.is_default:
        _clear_other_defaults(db, store_id)
    row = StorePrintProfile(
        store_id=int(store_id),
        tenant_id=int(tenant_id),
        name=body.name.strip(),
        brand=body.brand,
        cloud_sn=_s(body.cloud_sn) or None,
        cloud_device_key=_s(body.cloud_device_key) or None,
        paper_preset=body.paper_preset,
        paper_width_mm=body.paper_width_mm,
        paper_height_mm=body.paper_height_mm,
        local_printer_name_hint=_s(body.local_printer_name_hint) or None,
        margin_top_mm=body.margin_top_mm,
        margin_left_mm=body.margin_left_mm,
        is_default=body.is_default,
        is_active=body.is_active,
    )
    db.add(row)
    db.flush()
    if row.brand in CLOUD_PRINT_BRANDS:
        _register_cloud_printer(db, tenant_id, row)
    db.commit()
    db.refresh(row)
    return _profile_out(row)


def patch_store_print_profile(
    db: Session, *, store_id: int, profile_id: int, body: StorePrintProfilePatchIn
) -> StorePrintProfileOut:
    row = db.get(StorePrintProfile, int(profile_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="打印机不存在")
    if body.is_default is True:
        _clear_other_defaults(db, store_id, except_id=int(profile_id))
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "cloud_device_key":
            setattr(row, k, _s(v) or None)
        elif isinstance(v, str):
            setattr(row, k, v.strip())
        else:
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _profile_out(row)


def delete_store_print_profile(db: Session, *, store_id: int, profile_id: int) -> None:
    row = db.get(StorePrintProfile, int(profile_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="打印机不存在")
    row.is_active = False
    row.is_default = False
    db.commit()


def get_scene_settings(db: Session, *, store_id: int) -> list[StorePrintSceneSettingOut]:
    existing = {
        r.scene: r
        for r in db.scalars(
            select(StorePrintSceneSetting).where(StorePrintSceneSetting.store_id == int(store_id))
        ).all()
    }
    return [
        StorePrintSceneSettingOut(
            scene=scene,
            scene_label=SCENE_LABELS.get(scene, scene),
            profile_id=int(r.profile_id) if (r := existing.get(scene)) and r.profile_id else None,
            template_key=r.template_key if r else DEFAULT_SCENE_TEMPLATE[scene],
            copies_mode=(r.copies_mode if r else "per_unit"),  # type: ignore[arg-type]
        )
        for scene in PRINT_SCENES
    ]


def put_scene_settings(
    db: Session, *, store_id: int, settings: list[StorePrintSceneSettingOut]
) -> list[StorePrintSceneSettingOut]:
    valid_templates = {t["key"] for t in PRINT_TEMPLATES}
    for s in settings:
        if s.scene not in PRINT_SCENES:
            raise HTTPException(status_code=400, detail=f"未知场景：{s.scene}")
        if s.template_key not in valid_templates:
            raise HTTPException(status_code=400, detail=f"未知模板：{s.template_key}")
        if s.profile_id is not None:
            prof = db.get(StorePrintProfile, int(s.profile_id))
            if prof is None or int(prof.store_id) != int(store_id) or not prof.is_active:
                raise HTTPException(status_code=400, detail="打印机不存在或已停用")
        row = db.get(StorePrintSceneSetting, {"store_id": int(store_id), "scene": s.scene})
        if row is None:
            row = StorePrintSceneSetting(store_id=int(store_id), scene=s.scene)
            db.add(row)
        row.profile_id = int(s.profile_id) if s.profile_id else None
        row.template_key = s.template_key
        row.copies_mode = s.copies_mode
    db.commit()
    return get_scene_settings(db, store_id=store_id)


def _get_profile_for_scene(
    db: Session, *, store_id: int, scene: str, profile_id: int | None
) -> tuple[StorePrintProfile, str, str]:
    setting = db.get(StorePrintSceneSetting, {"store_id": int(store_id), "scene": scene})
    template_key = setting.template_key if setting else DEFAULT_SCENE_TEMPLATE.get(scene, "delivery_meal_full")
    copies_mode = setting.copies_mode if setting else "per_unit"
    pid = profile_id or (int(setting.profile_id) if setting and setting.profile_id else None)
    # 零售/商城未单独绑定时，回退使用配送标签打印机（同款备餐面单，避免重复配置）
    if pid is None and scene == "store_retail":
        delivery_setting = db.get(
            StorePrintSceneSetting, {"store_id": int(store_id), "scene": "delivery_sheet"}
        )
        if delivery_setting and delivery_setting.profile_id:
            pid = int(delivery_setting.profile_id)
            if setting is None:
                template_key = delivery_setting.template_key or DEFAULT_SCENE_TEMPLATE["store_retail"]
                copies_mode = delivery_setting.copies_mode or "per_unit"
    if pid is None:
        raise HTTPException(status_code=400, detail="请先在打印设置中绑定打印机")
    prof = db.get(StorePrintProfile, int(pid))
    if prof is None or int(prof.store_id) != int(store_id) or not prof.is_active:
        raise HTTPException(status_code=400, detail="打印机不存在或已停用")
    return prof, template_key, copies_mode


def resolve_print_config(
    db: Session, *, store_id: int, scene: str, profile_id: int | None = None, template_key: str | None = None
) -> StorePrintResolveOut:
    if scene not in PRINT_SCENES:
        raise HTTPException(status_code=400, detail="未知打印场景")
    try:
        prof, tk, cm = _get_profile_for_scene(db, store_id=store_id, scene=scene, profile_id=profile_id)
        if template_key:
            tk = template_key
        return StorePrintResolveOut(
            scene=scene,
            profile_id=int(prof.id),
            brand=prof.brand,
            brand_label=PRINT_BRANDS.get(prof.brand, prof.brand),
            template_key=tk,
            copies_mode=cm,  # type: ignore[arg-type]
            paper_width_mm=int(prof.paper_width_mm),
            paper_height_mm=int(prof.paper_height_mm),
            local_printer_name_hint=prof.local_printer_name_hint,
            configured=True,
        )
    except HTTPException:
        return StorePrintResolveOut(
            scene=scene,
            profile_id=None,
            brand=None,
            template_key=DEFAULT_SCENE_TEMPLATE.get(scene, ""),
            copies_mode="per_unit",
            configured=False,
        )


def _expand_items(items: list[LabelItemIn], copies_mode: str) -> list[LabelItemIn]:
    out: list[LabelItemIn] = []
    for item in items:
        if copies_mode == "per_order":
            out.append(item)
            continue
        for i in range(max(1, int(item.units or 1))):
            copy = item.model_copy(deep=True)
            copy.units = 1
            out.append(copy)
    return out


def _dispatch_cloud(db: Session, *, tenant_id: int, profile: StorePrintProfile, content: str) -> str:
    creds = _load_cloud_creds(db, tenant_id, profile.brand)
    sn = _s(profile.cloud_sn)
    if profile.brand == "feie_label":
        return feie_client.print_label(creds.feie_user, creds.feie_ukey, sn, content)
    if profile.brand == "xprinter_cloud_label":
        return xprinter_client.print_label(creds.xprinter_user, creds.xprinter_user_key, sn, content)
    if profile.brand == "yilian_k4":
        return yilian_client.print_content(
            creds.yilian_partner, creds.yilian_apikey, sn, _s(profile.cloud_device_key), content
        )
    raise HTTPException(status_code=400, detail="不支持的云打印品牌")


def create_print_job(
    db: Session, *, tenant_id: int, store_id: int, admin_username: str, body: StorePrintJobCreateIn
) -> StorePrintJobOut:
    prof, template_key, copies_mode = _get_profile_for_scene(
        db, store_id=store_id, scene=body.scene, profile_id=body.profile_id
    )
    if body.template_key:
        template_key = body.template_key
    expanded = _expand_items(body.items, copies_mode)
    job = StorePrintJob(
        store_id=int(store_id),
        tenant_id=int(tenant_id),
        scene=body.scene,
        profile_id=int(prof.id),
        template_key=template_key,
        brand=prof.brand,
        cloud_sn=prof.cloud_sn,
        item_count=len(expanded),
        status="pending",
        created_by_admin=admin_username,
    )
    db.add(job)
    db.flush()
    local_layouts: list[dict[str, Any]] = []
    provider_ids: list[str] = []
    for idx, item in enumerate(expanded):
        payload = render_label_payload(
            item,
            template_key,
            paper_width_mm=int(prof.paper_width_mm),
            paper_height_mm=int(prof.paper_height_mm),
            margin_top_mm=int(prof.margin_top_mm),
            margin_left_mm=int(prof.margin_left_mm),
            copies_mode=copies_mode,
        )
        if prof.brand == "local_label":
            if payload.lodop_layout:
                local_layouts.append(lodop_layout_to_dict(payload.lodop_layout))
            continue
        content = payload.feie_xp_content if prof.brand != "yilian_k4" else (payload.yilian_content or "")
        try:
            oid = _dispatch_cloud(db, tenant_id=tenant_id, profile=prof, content=content or "")
            provider_ids.append(oid)
        except Exception as e:
            job.status = "failed"
            job.error_msg = str(e)[:500]
            db.commit()
            raise HTTPException(status_code=502, detail=f"云打印失败：{e}") from e
        if idx < len(expanded) - 1:
            time.sleep(0.3)
    if prof.brand == "local_label":
        job.status = "pending_local"
        db.commit()
        payload_w = int(prof.paper_width_mm)
        payload_h = int(prof.paper_height_mm)
        if local_layouts:
            payload_w = int(local_layouts[0].get("paper_width_mm") or payload_w)
            payload_h = int(local_layouts[0].get("paper_height_mm") or payload_h)
        return StorePrintJobOut(
            job_id=int(job.id),
            driver="local_label",
            status="pending_local",
            local_payload={
                "paper_width_mm": payload_w,
                "paper_height_mm": payload_h,
                "local_printer_name_hint": prof.local_printer_name_hint,
                "layouts": local_layouts,
            },
        )
    job.status = "success"
    job.provider_order_id = provider_ids[0] if provider_ids else None
    db.commit()
    return StorePrintJobOut(
        job_id=int(job.id), driver=prof.brand, status="success", printed_count=len(expanded)
    )


def test_print_profile(db: Session, *, tenant_id: int, store_id: int, profile_id: int) -> StorePrintJobOut:
    prof = db.get(StorePrintProfile, int(profile_id))
    if prof is None or int(prof.store_id) != int(store_id) or not prof.is_active:
        raise HTTPException(status_code=404, detail="打印机不存在")
    payload = render_test_label(
        paper_width_mm=int(prof.paper_width_mm),
        paper_height_mm=int(prof.paper_height_mm),
        margin_top_mm=int(prof.margin_top_mm),
        margin_left_mm=int(prof.margin_left_mm),
        printer_name=prof.name,
    )
    if prof.brand == "local_label":
        layout = payload.lodop_layout
        return StorePrintJobOut(
            job_id=0,
            driver="local_label",
            status="pending_local",
            local_payload={
                "paper_width_mm": int(prof.paper_width_mm),
                "paper_height_mm": int(prof.paper_height_mm),
                "local_printer_name_hint": prof.local_printer_name_hint,
                "layouts": [lodop_layout_to_dict(layout)] if layout else [],
            },
        )
    content = payload.feie_xp_content if prof.brand != "yilian_k4" else (payload.yilian_content or "")
    try:
        oid = _dispatch_cloud(db, tenant_id=tenant_id, profile=prof, content=content or "")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"测试打印失败：{e}") from e
    return StorePrintJobOut(job_id=0, driver=prof.brand, status="success", printed_count=1)


def list_print_templates(scene: str | None = None, tenant_id: int | None = None) -> list[dict[str, Any]]:
    items = [t for t in PRINT_TEMPLATES if scene is None or t["scene"] == scene]
    if tenant_id is None:
        return list(items)
    tid = int(tenant_id)
    out: list[dict[str, Any]] = []
    for t in items:
        allowed = t.get("tenant_ids")
        if allowed and tid not in allowed:
            continue
        out.append(t)
    return out
