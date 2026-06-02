"""抖音核销记录：管理端查询。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.timeutil import shanghai_naive_range_for_calendar_day
from app.models.douyin.certificate_redemption import DouyinCertificateRedemption
from app.models.douyin.product_mapping import DouyinProductMapping
from app.models.member import Member
from app.schemas.douyin import DouyinRedemptionOut


def _format_amount(v) -> str | None:
    if v is None:
        return None
    return f"{v:.2f}"


def list_douyin_redemptions_paged(
    db: Session,
    *,
    store_id: int,
    page: int,
    page_size: int,
    member_phone: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[DouyinRedemptionOut], int]:
    q = select(DouyinCertificateRedemption).where(
        DouyinCertificateRedemption.store_id == int(store_id)
    )
    if status and status.strip():
        q = q.where(DouyinCertificateRedemption.status == status.strip())
    if date_from is not None:
        start, _ = shanghai_naive_range_for_calendar_day(date_from)
        q = q.where(DouyinCertificateRedemption.created_at >= start)
    if date_to is not None:
        _, end = shanghai_naive_range_for_calendar_day(date_to)
        q = q.where(DouyinCertificateRedemption.created_at < end)

    phone = (member_phone or "").strip()
    if phone:
        q = q.join(Member, Member.id == DouyinCertificateRedemption.member_id).where(
            Member.phone.like(f"%{phone}%")
        )

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(DouyinCertificateRedemption.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    mapping_names: dict[int, str] = {}
    mapping_ids = {int(r.mapping_id) for r in rows if r.mapping_id is not None}
    if mapping_ids:
        maps = db.scalars(
            select(DouyinProductMapping).where(DouyinProductMapping.id.in_(mapping_ids))
        ).all()
        mapping_names = {int(m.id): str(m.display_name) for m in maps}

    member_ids = {int(r.member_id) for r in rows}
    members = {}
    if member_ids:
        for m in db.scalars(select(Member).where(Member.id.in_(member_ids))).all():
            members[int(m.id)] = m

    out: list[DouyinRedemptionOut] = []
    for row in rows:
        mem = members.get(int(row.member_id))
        out.append(
            DouyinRedemptionOut(
                id=int(row.id),
                member_id=int(row.member_id),
                member_phone=str(mem.phone) if mem else None,
                member_name=str(mem.name) if mem else None,
                code_masked=row.code_masked,
                douyin_order_id=row.douyin_order_id,
                certificate_id=str(row.certificate_id),
                douyin_product_id=row.douyin_product_id,
                douyin_sku_id=row.douyin_sku_id,
                douyin_product_title=row.douyin_product_title,
                mapping_display_name=mapping_names.get(int(row.mapping_id)) if row.mapping_id else None,
                grant_type=row.grant_type,
                grant_target_id=int(row.grant_target_id) if row.grant_target_id is not None else None,
                grant_result_kind=row.grant_result_kind,
                grant_result_id=int(row.grant_result_id) if row.grant_result_id is not None else None,
                status=str(row.status),
                error_msg=row.error_msg,
                amount_yuan=_format_amount(row.amount_yuan),
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
        )
    return out, int(total)
