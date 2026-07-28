"""会员批量导入：预览校验与确认入库（租户/门店隔离）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.schemas.member_import import (
    MemberImportConfirmIn,
    MemberImportConfirmResultOut,
    MemberImportPreviewOut,
    MemberImportPreviewRowOut,
    MemberImportPreviewSummaryOut,
    MemberImportRowData,
)
from app.services.admin.member_import_parser import (
    RawMemberImportRow,
    normalize_raw_row,
    parse_member_import_xlsx,
)
from app.services.member.member_address_service import upsert_default_address_after_register
from app.services.shared import amap
from app.services.shared.region_assignment import assign_region_for_coords


def _merge_rows_by_phone(raw_rows: list[RawMemberImportRow]) -> list[RawMemberImportRow]:
    """
    同一文件内相同手机号合并为一行（取首次出现行的基础信息，剩余次数取 max）。
    避免表格重复填写导致重复入库。
    """
    buckets: dict[str, list[RawMemberImportRow]] = {}
    order: list[str] = []
    for row in raw_rows:
        from app.services.admin.member_import_parser import normalize_phone

        phone = normalize_phone(row.phone_raw)
        key = phone if phone else f"__row_{row.row_no}"
        if key not in buckets:
            order.append(key)
            buckets[key] = []
        buckets[key].append(row)

    merged: list[RawMemberImportRow] = []
    for key in order:
        group = buckets[key]
        if len(group) == 1:
            merged.append(group[0])
            continue
        # 以首行为主，剩余次数取最大值
        base = group[0]
        max_balance = base.balance_raw
        for r in group[1:]:
            from app.services.admin.member_import_parser import parse_int_cell

            b0 = parse_int_cell(max_balance)
            b1 = parse_int_cell(r.balance_raw)
            if b1 is not None and (b0 is None or b1 > b0):
                max_balance = r.balance_raw
        merged.append(
            RawMemberImportRow(
                row_no=min(g.row_no for g in group),
                name=base.name,
                phone_raw=base.phone_raw,
                plan_type_raw=base.plan_type_raw,
                address=base.address,
                balance_raw=max_balance,
                meal_quota_total_raw=base.meal_quota_total_raw,
                daily_meal_units_raw=base.daily_meal_units_raw,
                delivery_start_raw=base.delivery_start_raw,
                store_pickup_raw=base.store_pickup_raw,
                delivery_deferred_raw=base.delivery_deferred_raw,
                remarks=base.remarks,
            )
        )
    return merged


def _existing_phones_in_store(db: Session, store_id: int, phones: list[str]) -> set[str]:
    """批量查询当前门店已存在的手机号（不含软删）。"""
    if not phones:
        return set()
    rows = db.scalars(
        select(Member.phone).where(
            Member.store_id == int(store_id),
            Member.phone.in_(phones),
            Member.deleted_at.is_(None),
        )
    ).all()
    return {str(p) for p in rows}


def build_member_import_preview(
    db: Session,
    *,
    file_bytes: bytes,
    tenant_id: int,
    store_id: int,
) -> MemberImportPreviewOut:
    """解析上传文件并生成预览（含行级校验与重复手机号检测）。"""
    raw_rows, file_errors = parse_member_import_xlsx(file_bytes)
    if file_errors:
        return MemberImportPreviewOut(
            summary=MemberImportPreviewSummaryOut(total=0, ready=0, error=len(file_errors), skip=0),
            rows=[
                MemberImportPreviewRowOut(row_no=1, status="error", messages=file_errors, data=None),
            ],
        )

    merged = _merge_rows_by_phone(raw_rows)
    ready_phones: list[str] = []
    parsed: list[tuple[RawMemberImportRow, MemberImportRowData | None, list[str]]] = []

    for raw in merged:
        normalized, errs = normalize_raw_row(raw)
        if errs:
            parsed.append((raw, None, errs))
            continue
        assert normalized is not None
        data = MemberImportRowData.model_validate(normalized)
        parsed.append((raw, data, []))
        ready_phones.append(data.phone)

    existing = _existing_phones_in_store(db, store_id, ready_phones)

    final_rows: list[MemberImportPreviewRowOut] = []
    ready_count = error_count = skip_count = 0
    for raw, data, errs in parsed:
        if errs:
            final_rows.append(
                MemberImportPreviewRowOut(row_no=raw.row_no, status="error", messages=errs, data=None)
            )
            error_count += 1
            continue
        assert data is not None
        if data.phone in existing:
            final_rows.append(
                MemberImportPreviewRowOut(
                    row_no=raw.row_no,
                    status="skip",
                    messages=[f"手机号 {data.phone} 在本门店已存在，跳过"],
                    data=data,
                )
            )
            skip_count += 1
        else:
            final_rows.append(
                MemberImportPreviewRowOut(row_no=raw.row_no, status="ready", messages=[], data=data)
            )
            ready_count += 1

    return MemberImportPreviewOut(
        summary=MemberImportPreviewSummaryOut(
            total=len(merged),
            ready=ready_count,
            error=error_count,
            skip=skip_count,
        ),
        rows=final_rows,
    )


def _insert_one_member(
    db: Session,
    *,
    row: MemberImportRowData,
    tenant_id: int,
    store_id: int,
) -> None:
    """写入单条会员及其默认地址（含地理编码与自动划区）；不 commit。"""
    # 地理编码：自提类地址跳过
    lng, lat, region_id = None, None, None
    if not row.store_pickup:
        coords = amap.geocode_address(row.address)
        if coords:
            lng, lat = coords[0], coords[1]
            r = assign_region_for_coords(db, lng, lat, tenant_id=int(tenant_id))
            region_id = int(r.id) if r else None

    is_active = not row.delivery_deferred and row.balance > 0

    member = Member(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        phone=row.phone,
        name=row.name,
        wechat_name=row.name,
        remarks=row.remarks,
        balance=row.balance,
        daily_meal_units=row.daily_meal_units,
        meal_quota_total=row.meal_quota_total,
        plan_type=row.plan_type.value,
        is_active=is_active,
        is_leaved_tomorrow=False,
        delivery_start_date=row.delivery_start_date,
        delivery_deferred=row.delivery_deferred,
        store_pickup=row.store_pickup,
    )
    db.add(member)
    db.flush()

    upsert_default_address_after_register(
        db,
        member_id=member.id,
        contact_name=row.name,
        contact_phone=row.phone,
        address_line=row.address,
        remarks=row.remarks,
        delivery_region_id=region_id,
        lng=lng,
        lat=lat,
    )


def confirm_member_import(
    db: Session,
    *,
    body: MemberImportConfirmIn,
    tenant_id: int,
    store_id: int,
    operator: str,
) -> MemberImportConfirmResultOut:
    """
    确认入库：对每条数据再次校验手机号是否已存在，逐条写入。
    operator 预留审计扩展，当前写入 member 默认 updated_at。
    """
    _ = operator
    inserted = skipped = failed = 0
    messages: list[str] = []

    # 请求内去重：同一手机号只保留首条
    seen_phones: set[str] = set()
    unique_rows: list[MemberImportRowData] = []
    for row in body.rows:
        if row.phone in seen_phones:
            skipped += 1
            messages.append(f"请求内重复手机号 {row.phone}，已跳过")
            continue
        seen_phones.add(row.phone)
        unique_rows.append(row)

    phones = [r.phone for r in unique_rows]
    existing = _existing_phones_in_store(db, store_id, phones)

    for row in unique_rows:
        if row.phone in existing:
            skipped += 1
            messages.append(f"手机号 {row.phone} 已存在，跳过")
            continue
        try:
            with db.begin_nested():
                _insert_one_member(db, row=row, tenant_id=tenant_id, store_id=store_id)
            existing.add(row.phone)
            inserted += 1
        except Exception as exc:
            failed += 1
            messages.append(f"手机号 {row.phone} 写入失败：{exc}")

    if inserted > 0:
        db.commit()
    else:
        db.rollback()

    return MemberImportConfirmResultOut(
        inserted=inserted,
        skipped=skipped,
        failed=failed,
        messages=messages[:50],
    )
