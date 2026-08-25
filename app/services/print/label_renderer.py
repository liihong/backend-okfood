"""标签渲染：统一 LabelItem → 飞鹅/芯烨 XML、易联云排版、Lodop 布局。"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from app.schemas.store_print import (
    DELIVERY_ENJOY_MEAL_KEY,
    DELIVERY_MEAL_FULL_TIPS,
    ENJOY_MEAL_GREETING,
    ENJOY_MEAL_PAPER_HEIGHT_MM,
    ENJOY_MEAL_PAPER_WIDTH_MM,
    ENJOY_MEAL_TIP_1,
    ENJOY_MEAL_TIP_2,
    LabelItemIn,
)


@dataclass
class LodopTextBlock:
    x_mm: float
    y_mm: float
    text: str
    font_size_pt: int = 10
    bold: bool = False
    width_mm: float | None = None
    height_mm: float | None = None
    align: str = "left"


@dataclass
class LodopBarcodeBlock:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    code: str
    show_text: bool = True
    code_type: str = "128Auto"


@dataclass
class LodopLayout:
    paper_width_mm: int
    paper_height_mm: int
    margin_top_mm: int
    margin_left_mm: int
    blocks: list[LodopTextBlock] = field(default_factory=list)
    content_height_mm: float | None = None
    layout_style: str = "default"
    header_text: str = ""
    header_right_text: str = ""
    table_html: str = ""
    barcodes: list[LodopBarcodeBlock] = field(default_factory=list)


@dataclass
class RenderedPrintPayload:
    feie_xp_content: str | None = None
    yilian_content: str | None = None
    lodop_layout: LodopLayout | None = None


def _mm_to_dot(mm: float, dpi: int = 203) -> int:
    return max(0, int(round(mm * dpi / 25.4)))


def _xml_text(x: int, y: int, text: str, *, w: int = 1, h: int = 1, font: int = 12) -> str:
    safe = escape(text or "", quote=False)
    return f'<TEXT x="{x}" y="{y}" font="{font}" w="{w}" h="{h}" r="0">{safe}</TEXT>'


@dataclass
class _RenderLine:
    """渲染用单行；right_text 非空时为左右分栏同一行。"""

    text: str = ""
    right_text: str = ""
    font_pt: int = 10
    bold: bool = False
    line_mm: float = 5.5
    align: str = "left"
    highlight: bool = False


def _estimate_text_dots(text: str, *, font: int = 9) -> int:
    """飞鹅/芯烨标签：估算文本占位 dot（右对齐用）。"""
    per = 11 if font >= 12 else 9
    return max(0, len(text or "")) * per


def _format_meal_category_short(raw: str) -> str:
    """餐别短文案：午晚餐卡 → 午+晚，午餐+果蔬汁卡 → 午+果蔬汁。"""
    s = (raw or "").strip().replace("卡", "").replace(" ", "")
    if not s:
        return "午"
    s = s.replace("午餐", "午").replace("晚餐", "晚")
    if s in ("午晚", "午晚餐"):
        return "午+晚"
    if "午晚" in s and "+" not in s:
        return "午+晚"
    return s


def _sf_barcode_value(item: LabelItemIn) -> str:
    sf = (item.sf_order_id or "").strip()
    if sf:
        return sf
    shop = (item.shop_order_id or item.order_no or "").strip()
    return shop


def _order_no_display(item: LabelItemIn) -> str:
    kind = (item.order_kind or "").strip().lower()
    if kind in ("retail", "mall"):
        no = (item.order_no or "").strip()
        return no or "—"
    # 订阅配送：面单「订单号」展示大表备餐短号（片区编码+序号），顺丰 shop_order_id 仅用于推单/条码兜底
    prep = (item.order_no or "").strip()
    if prep:
        return prep
    shop = (item.shop_order_id or "").strip()
    return shop or "—"


def _uses_sf_waybill_layout(item: LabelItemIn, template_key: str) -> bool:
    """备餐面单（顺丰同城风格）布局：订阅配送、零售、商城均可用。"""
    if template_key != "delivery_meal_full":
        return False
    kind = (item.order_kind or "").strip().lower()
    if kind in ("retail", "mall"):
        return True
    return not (item.product_title or "").strip()


def _uses_enjoy_meal_layout(template_key: str) -> bool:
    """Hello轻厨竖版袋贴。"""
    return template_key == DELIVERY_ENJOY_MEAL_KEY


def _header_right_label(item: LabelItemIn) -> str:
    """门店名称行右侧：零售/商城订单类型，订阅仍为配送/自提。"""
    kind = (item.order_kind or "").strip().lower()
    if kind == "retail":
        return "零售订单"
    if kind == "mall":
        return "商城订单"
    return "自提" if item.store_pickup else "配送"


def _meal_row_label(item: LabelItemIn) -> str:
    kind = (item.order_kind or "").strip().lower()
    return "餐品" if kind in ("retail", "mall") else "餐别"


def _product_detail_text(item: LabelItemIn) -> str:
    """零售/商城：餐品详情（商品名，多份带数量）。"""
    title = (item.product_title or item.meal_category or "").strip()
    if not title:
        return "—"
    qty = max(1, int(item.units or 1))
    if qty > 1:
        return f"{title} ×{qty}"
    return title


def _meal_row_value(item: LabelItemIn) -> str:
    kind = (item.order_kind or "").strip().lower()
    if kind in ("retail", "mall"):
        return _product_detail_text(item)
    return _format_meal_category_short(item.meal_category or "午餐卡")


def _fulfillment_mode_label(item: LabelItemIn) -> str:
    """履约方式：门店名称行右侧显示（兼容旧调用）。"""
    return _header_right_label(item)


def _build_sf_waybill_table_html(item: LabelItemIn) -> str:
    """顺丰同城风格表格区 HTML。"""
    region = (item.region or "").strip() or "未分配片区"
    name = (item.name or "").strip()
    phone_disp = _mask_phone_display("", item.phone_masked)
    member_line = name
    if phone_disp:
        member_line = f"{name} · {phone_disp}" if name else phone_disp
    meal_label = _meal_row_label(item)
    meal_val = _meal_row_value(item)
    units_n = max(1, int(item.units or 1))
    remark = (item.remark or "").strip() or "无"
    tips = DELIVERY_MEAL_FULL_TIPS
    order_no = _order_no_display(item)
    border = "0.25mm solid #111"
    cell = f"border:{border};padding:1.2mm 2mm;word-break:break-all;line-height:1.25;"
    cell_order = (
        f"border:{border};padding:2.8mm 2mm;word-break:break-all;"
        f"line-height:1.45;font-size:12px;font-weight:700;"
    )
    cell_lg = f"border:{border};padding:3.5mm 2mm;word-break:break-all;line-height:1.45;"
    rows: list[str] = [
        f'<tr><td style="{cell_order}">订单号：{escape(order_no)}</td></tr>',
        (
            f'<tr><td style="{cell}text-align:center;font-size:17px;font-weight:700;'
            f'padding:2.5mm 1mm;">{escape(region)}</td></tr>'
        ),
        (
            f'<tr><td style="{cell_lg}font-size:14px;font-weight:700;">'
            f'{escape(member_line or "—")}</td></tr>'
        ),
        (
            f'<tr><td style="{cell_lg}font-size:16px;font-weight:700;">'
            f'{escape(meal_label)}：{escape(meal_val)}</td></tr>'
        ),
        (
            f'<tr><td style="{cell_lg}font-size:16px;font-weight:700;">'
            f'数量：{units_n}份</td></tr>'
        ),
        (
            f'<tr><td style="{cell_lg}font-size:16px;font-weight:700;">'
            f'备注：{escape(remark[:120])}</td></tr>'
        ),
        f'<tr><td style="{cell}font-size:9px;">tips：{escape(tips)}</td></tr>',
    ]
    table = (
        f'<table style="width:100%;border-collapse:collapse;border:{border};">'
        + "".join(rows)
        + "</table>"
    )
    sf = (item.sf_order_id or "").strip()
    if not sf:
        return table
    # 虚线分隔（条码由 Lodop LinkedItem 紧跟表格，不在 HTML 里占位）
    return (
        table
        + f'<div style="margin-top:1.5mm;border-top:0.2mm dashed #bbb;height:0;line-height:0;font-size:0;">&nbsp;</div>'
    )


def _build_meal_full_lines(item: LabelItemIn) -> list[_RenderLine]:
    """云打印/易联云：顺丰面单字段顺序（纯文本）。"""
    store = (item.store_name or "OK饭").strip() or "OK饭"
    region = (item.region or "").strip()
    name = (item.name or "").strip()
    phone_disp = _mask_phone_display("", item.phone_masked)
    member_line = name
    if phone_disp:
        member_line = f"{name} · {phone_disp}" if name else phone_disp
    remark = (item.remark or "").strip() or "无"
    meal_label = _meal_row_label(item)
    meal_val = _meal_row_value(item)
    units_n = max(1, int(item.units or 1))
    sf_no = (item.sf_order_id or "").strip()
    lines: list[_RenderLine] = [
        _RenderLine(
            store,
            font_pt=12,
            bold=True,
            line_mm=5.5,
            align="center",
            right_text=_header_right_label(item),
        ),
        _RenderLine(
            f"订单号：{_order_no_display(item)}",
            font_pt=12,
            bold=True,
            line_mm=6.5,
        ),
        _RenderLine(region or "未分配片区", font_pt=18, bold=True, line_mm=9, align="center"),
        _RenderLine(member_line or "—", font_pt=14, bold=True, line_mm=7.5),
        _RenderLine(f"{meal_label}：{meal_val}", font_pt=16, bold=True, line_mm=8),
        _RenderLine(f"数量：{units_n}份", font_pt=16, bold=True, line_mm=8),
        _RenderLine(f"备注：{remark[:100]}", font_pt=16, bold=True, line_mm=10),
        _RenderLine(f"tips：{DELIVERY_MEAL_FULL_TIPS}", font_pt=9, bold=False, line_mm=5.5),
    ]
    if sf_no:
        lines.append(_RenderLine(f"顺丰单号：{sf_no}", font_pt=8, bold=False, line_mm=5, align="center"))
    return lines


def _to_lodop_layout_sf_waybill(
    item: LabelItemIn,
    *,
    paper_width_mm: int,
    paper_height_mm: int,
    margin_top_mm: int,
    margin_left_mm: int,
) -> LodopLayout:
    """76×130 顺丰同城风格：门店名 + 表格 + 页底顺丰条码（整页 130mm，单页输出）。"""
    margin_l = max(margin_left_mm, 2)
    store = (item.store_name or "OK饭").strip() or "OK饭"
    barcode_h = 14.0
    sf = (item.sf_order_id or "").strip()

    table_html = _build_sf_waybill_table_html(item)
    barcodes: list[LodopBarcodeBlock] = []
    if sf:
        barcodes.append(
            LodopBarcodeBlock(
                x_mm=float(margin_l),
                y_mm=0.0,
                width_mm=float(paper_width_mm) - float(margin_l) * 2,
                height_mm=barcode_h,
                code=sf,
                show_text=True,
            )
        )

    layout = LodopLayout(
        paper_width_mm=paper_width_mm,
        paper_height_mm=paper_height_mm,
        margin_top_mm=margin_top_mm,
        margin_left_mm=int(margin_l),
        blocks=[],
        layout_style="sf_waybill",
        header_text=store,
        header_right_text=_header_right_label(item),
        table_html=table_html,
        barcodes=barcodes,
    )
    layout.content_height_mm = float(paper_height_mm)
    return layout


def _format_date_slash(raw: str) -> str:
    """袋贴日期：2026-07-24 → 2026/07/24。"""
    s = (raw or "").strip()
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        return f"{s[:4]}/{s[5:7]}/{s[8:10]}"
    return s or ""


def _format_meal_category_enjoy(raw: str) -> str:
    """袋贴餐别：午晚餐卡 → 午+晚，午餐+果蔬汁卡 → 午+果。"""
    s = _format_meal_category_short(raw)
    s = s.replace("果蔬汁", "果").replace("果蔬", "果")
    return s or "—"


def _enjoy_meal_name_value(item: LabelItemIn) -> str:
    return (item.name or "").strip() or "—"


def _enjoy_meal_meal_value(item: LabelItemIn) -> str:
    kind = (item.order_kind or "").strip().lower()
    if kind in ("retail", "mall"):
        title = (item.product_title or item.meal_category or "").strip()
        return title or "—"
    return _format_meal_category_enjoy(item.meal_category or "午餐卡")


def _build_enjoy_meal_lines(item: LabelItemIn) -> list[_RenderLine]:
    """75×50 单张：左上角起排，不含加好友二维码。"""
    meal_label = _meal_row_label(item)
    date_s = _format_date_slash(item.delivery_date)
    return [
        _RenderLine(f"{ENJOY_MEAL_GREETING} :)", font_pt=11, bold=True, line_mm=6.5),
        _RenderLine(f"姓名：{_enjoy_meal_name_value(item)}", font_pt=15, bold=True, line_mm=8),
        _RenderLine(f"{meal_label}：{_enjoy_meal_meal_value(item)}", font_pt=15, bold=True, line_mm=8),
        _RenderLine(ENJOY_MEAL_TIP_1, font_pt=8, bold=False, line_mm=5),
        _RenderLine(ENJOY_MEAL_TIP_2, font_pt=8, bold=False, line_mm=5.5),
        _RenderLine(f"日期：{date_s}" if date_s else "日期：—", font_pt=10, bold=True, line_mm=5.5),
    ]


def _to_lodop_layout_enjoy_meal(
    item: LabelItemIn,
    *,
    paper_width_mm: int,
    paper_height_mm: int,
    margin_top_mm: int,
    margin_left_mm: int,
) -> LodopLayout:
    """75×50 袋贴：绝对坐标从左上角起，高度锁定 50mm，避免连打多张。"""
    width_mm = ENJOY_MEAL_PAPER_WIDTH_MM
    height_mm = ENJOY_MEAL_PAPER_HEIGHT_MM
    x = 1.5
    y = 1.5
    content_w = max(20.0, float(width_mm) - x * 2)
    blocks: list[LodopTextBlock] = []
    for ln in _build_enjoy_meal_lines(item):
        blocks.append(
            LodopTextBlock(
                x_mm=x,
                y_mm=y,
                text=ln.text,
                font_size_pt=ln.font_pt,
                bold=ln.bold,
                width_mm=content_w,
                height_mm=ln.line_mm,
                align="left",
            )
        )
        y += ln.line_mm
        if y > height_mm - 1.5:
            break
    layout = LodopLayout(
        paper_width_mm=width_mm,
        paper_height_mm=height_mm,
        margin_top_mm=1,
        margin_left_mm=1,
        blocks=blocks,
        layout_style="enjoy_meal",
        header_text=ENJOY_MEAL_GREETING,
        table_html="",
        barcodes=[],
    )
    layout.content_height_mm = float(height_mm)
    return layout


def _append_feie_line(
    parts: list[str],
    *,
    ln: _RenderLine,
    x: int,
    y: int,
    w_dot: int,
    margin_left_mm: int,
) -> int:
    """写入一行飞鹅/芯烨 markup，返回下一行 y。"""
    font = 12 if ln.font_pt >= 13 else (11 if ln.font_pt >= 11 else 9)
    w_scale = 2 if ln.font_pt >= 15 else (1 if ln.font_pt >= 12 else 1)
    h_scale = 2 if ln.font_pt >= 15 else 1

    if ln.right_text:
        if ln.align == "center":
            cx = max(x, (w_dot - _estimate_text_dots(ln.text, font=font)) // 2)
            parts.append(_xml_text(cx, y, ln.text, w=1, h=1, font=font))
        else:
            parts.append(_xml_text(x, y, ln.text, w=1, h=1, font=font))
        right_x = max(x, w_dot - _mm_to_dot(margin_left_mm) - _estimate_text_dots(ln.right_text, font=font))
        parts.append(_xml_text(right_x, y, ln.right_text, w=1, h=1, font=font))
    elif ln.align == "center":
        cx = max(x, (w_dot - _estimate_text_dots(ln.text, font=font)) // 2)
        parts.append(_xml_text(cx, y, ln.text, w=w_scale, h=h_scale, font=font))
    else:
        parts.append(_xml_text(x, y, ln.text, w=w_scale, h=h_scale, font=font))
    return y + _mm_to_dot(ln.line_mm)


def _lodop_block(
    ln: _RenderLine,
    *,
    x: float,
    y: float,
    width_mm: float,
    align: str | None = None,
) -> LodopTextBlock:
    """单行 → Lodop 块（height_mm 与排版行高一致，避免预览被裁切）。"""
    return LodopTextBlock(
        x_mm=x,
        y_mm=y,
        text=ln.text,
        font_size_pt=ln.font_pt,
        bold=ln.bold or ln.highlight,
        width_mm=width_mm,
        height_mm=ln.line_mm,
        align=align or ln.align,
    )


def _calc_content_height_mm(
    blocks: list[LodopTextBlock],
    *,
    margin_bottom_mm: float = 4.0,
    min_mm: float = 50.0,
    max_mm: float | None = None,
) -> float:
    """按块实际占位计算打印高度，避免整页留白。"""
    bottom = 0.0
    for b in blocks:
        bottom = max(bottom, float(b.y_mm) + float(b.height_mm or 5))
    height = bottom + margin_bottom_mm
    if max_mm is not None:
        height = min(height, float(max_mm))
    return max(min_mm, height)


def _finalize_lodop_layout(
    layout: LodopLayout,
    *,
    paper_height_mm: int,
    margin_bottom_mm: float = 4.0,
) -> LodopLayout:
    layout.content_height_mm = _calc_content_height_mm(
        layout.blocks,
        margin_bottom_mm=margin_bottom_mm,
        max_mm=float(paper_height_mm),
    )
    return layout


def _append_lodop_line(
    blocks: list[LodopTextBlock],
    *,
    ln: _RenderLine,
    y: float,
    x: float,
    content_w: float,
    paper_width_mm: int,
    margin_left_mm: int,
    extra_indent_mm: float = 0,
) -> float:
    """写入 Lodop 块，返回下一行 y。extra_indent_mm 仅作用于左对齐行（中间信息区）。"""
    indent = extra_indent_mm if ln.align == "left" else 0.0
    block_x = x + indent
    block_w = max(12.0, content_w - indent)
    if ln.right_text:
        half = block_w * 0.48
        blocks.append(_lodop_block(ln, x=block_x, y=y, width_mm=half))
        blocks.append(
            LodopTextBlock(
                x_mm=block_x + half,
                y_mm=y,
                text=ln.right_text,
                font_size_pt=ln.font_pt,
                bold=ln.bold,
                width_mm=block_w - half,
                height_mm=ln.line_mm,
                align="right",
            )
        )
    elif ln.align == "center":
        blocks.append(_lodop_block(ln, x=x, y=y, width_mm=content_w, align="center"))
    elif ln.align == "right":
        blocks.append(_lodop_block(ln, x=block_x, y=y, width_mm=block_w, align="right"))
    else:
        blocks.append(_lodop_block(ln, x=block_x, y=y, width_mm=block_w))
    return y + ln.line_mm


def _format_date_cn(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        y, mo, d = s[:4], s[5:7], s[8:10]
        return f"{y}年{mo}月{d}日"
    return s or ""


def _mask_phone_display(phone: str, phone_masked: str) -> str:
    masked = (phone_masked or "").strip()
    if masked:
        return masked
    p = (phone or "").strip()
    if len(p) >= 11:
        return f"{p[:3]}****{p[-4:]}"
    if len(p) >= 7:
        return f"{p[:3]}****{p[-4:]}"
    return p


def _plan_type_label(plan_type: str) -> str:
    s = (plan_type or "").strip()
    if not s:
        return "—"
    return s


def _build_lines(item: LabelItemIn, template_key: str) -> list[tuple[str, int, bool]]:
    if _uses_sf_waybill_layout(item, template_key):
        return [(ln.text, 2 if ln.bold and ln.font_pt >= 12 else 1, ln.bold) for ln in _build_meal_full_lines(item)]
    if _uses_enjoy_meal_layout(template_key):
        return [(ln.text, 2 if ln.bold and ln.font_pt >= 12 else 1, ln.bold) for ln in _build_enjoy_meal_lines(item)]

    lines: list[tuple[str, int, bool]] = []
    region = (item.region or "").strip()
    if template_key == "delivery_large_region":
        lines.append((region or "未分配片区", 3, True))
    elif region:
        lines.append((region, 2, True))

    if item.product_title:
        if template_key == "retail_simple":
            lines.append((item.product_title, 2, True))
            if item.units:
                lines.append((f"x{item.units}", 2, True))
            if item.name:
                lines.append((item.name, 1, False))
            if item.phone_tail:
                lines.append((f"尾号 {item.phone_tail}", 1, False))
        elif template_key == "retail_pickup" or item.store_pickup:
            lines.append(("【自提】", 2, True))
            lines.append((item.product_title, 1, True))
            lines.append((f"数量 {item.units}", 1, False))
            if item.name:
                lines.append((item.name, 1, False))
            if item.delivery_date:
                lines.append((f"取货日 {item.delivery_date}", 1, False))
            if item.order_no:
                lines.append((f"#{item.order_no}", 1, False))
        else:
            if region:
                lines.append((region, 2, True))
            if item.address:
                lines.append((item.address, 1, False))
            lines.append((item.product_title, 1, True))
            lines.append((f"数量 {item.units}", 1, False))
            if item.name:
                contact = item.name
                if item.phone_tail:
                    contact += f" ·{item.phone_tail}"
                lines.append((contact, 1, False))
    else:
        addr = (item.address or "").strip()
        name = (item.name or "").strip()
        if template_key == "delivery_compact":
            head = " ".join(x for x in [addr, name] if x)
            if head:
                lines.append((head, 1, True))
            tail = item.phone_tail
            if item.units:
                tail = f"{item.units}份" + (f" ·{tail}" if tail else "")
            if tail:
                lines.append((tail, 1, False))
        else:
            if addr:
                line = addr
                if name:
                    line += f" {name}"
                lines.append((line, 1, True))
            elif name:
                lines.append((name, 1, True))
            if item.phone_tail:
                lines.append((f"·{item.phone_tail}", 1, False))
            if item.units:
                lines.append((f"{item.units} 份", 2, True))

    remark = (item.remark or "").strip()
    if remark:
        lines.append((f"备注：{remark}"[:80], 1, False))

    footer_parts: list[str] = []
    if item.delivery_date:
        footer_parts.append(item.delivery_date)
    if item.route_seq is not None:
        footer_parts.append(f"#{item.route_seq}")
    if footer_parts:
        lines.append(("  ".join(footer_parts), 1, False))

    return lines


def _to_feie_xp_xml(
    item: LabelItemIn,
    template_key: str,
    *,
    paper_width_mm: int,
    paper_height_mm: int,
    margin_top_mm: int,
    margin_left_mm: int,
) -> str:
    w_dot = _mm_to_dot(paper_width_mm)
    h_dot = _mm_to_dot(paper_height_mm)
    parts = [f"<SIZE>{w_dot},{h_dot}</SIZE>"]
    y = _mm_to_dot(margin_top_mm)
    x = _mm_to_dot(margin_left_mm)

    if _uses_sf_waybill_layout(item, template_key):
        sf = (item.sf_order_id or "").strip()
        for ln in _build_meal_full_lines(item):
            # 底部顺丰单号改条码输出，避免与正文重复
            if sf and (ln.text or "").startswith("顺丰单号："):
                continue
            y = _append_feie_line(
                parts,
                ln=ln,
                x=x,
                y=y,
                w_dot=w_dot,
                margin_left_mm=margin_left_mm,
            )
            if y > h_dot - _mm_to_dot(4):
                break
        if sf and y <= h_dot - _mm_to_dot(14):
            bc_h = _mm_to_dot(12)
            parts.append(
                f'<BC128 x="{x}" y="{y}" h="{bc_h}" s="1" r="0">{escape(sf, quote=False)}</BC128>'
            )
        return "".join(parts)

    if _uses_enjoy_meal_layout(template_key):
        for ln in _build_enjoy_meal_lines(item):
            y = _append_feie_line(
                parts,
                ln=ln,
                x=x,
                y=y,
                w_dot=w_dot,
                margin_left_mm=margin_left_mm,
            )
            if y > h_dot - _mm_to_dot(4):
                break
        return "".join(parts)

    line_h = _mm_to_dot(5)
    for text, scale, _bold in _build_lines(item, template_key):
        font = 12 if scale >= 2 else 9
        parts.append(_xml_text(x, y, text, w=min(scale, 2), h=min(scale, 2), font=font))
        y += line_h * max(1, scale // 2 + 1)
        if y > h_dot - line_h:
            break
    return "".join(parts)


def _to_yilian_content(item: LabelItemIn, template_key: str) -> str:
    if _uses_sf_waybill_layout(item, template_key):
        parts: list[str] = []
        for ln in _build_meal_full_lines(item):
            if ln.right_text:
                parts.append(f"{ln.text}    {ln.right_text}<BR>")
            elif ln.highlight:
                parts.append(f"<FS><BOLD>{ln.text}</BOLD></FS><BR>")
            elif ln.bold or ln.font_pt >= 12:
                parts.append(f"<FS>{ln.text}</FS><BR>")
            else:
                parts.append(f"{ln.text}<BR>")
        return "".join(parts)

    if _uses_enjoy_meal_layout(template_key):
        parts: list[str] = []
        for ln in _build_enjoy_meal_lines(item):
            if ln.bold or ln.font_pt >= 16:
                parts.append(f"<FS2><BOLD>{ln.text}</BOLD></FS2><BR>")
            elif ln.bold or ln.font_pt >= 12:
                parts.append(f"<FS>{ln.text}</FS><BR>")
            else:
                parts.append(f"{ln.text}<BR>")
        return "".join(parts)

    parts = []
    for text, scale, bold in _build_lines(item, template_key):
        if scale >= 2 or bold:
            parts.append(f"<FS>{text}</FS><BR>")
        else:
            parts.append(f"{text}<BR>")
    return "".join(parts)


def _to_lodop_layout(
    item: LabelItemIn,
    template_key: str,
    *,
    paper_width_mm: int,
    paper_height_mm: int,
    margin_top_mm: int,
    margin_left_mm: int,
) -> LodopLayout:
    blocks: list[LodopTextBlock] = []
    y = float(margin_top_mm)
    x = float(margin_left_mm)
    content_w = float(paper_width_mm - margin_left_mm * 2)

    if _uses_sf_waybill_layout(item, template_key):
        return _to_lodop_layout_sf_waybill(
            item,
            paper_width_mm=paper_width_mm,
            paper_height_mm=paper_height_mm,
            margin_top_mm=margin_top_mm,
            margin_left_mm=margin_left_mm,
        )

    if _uses_enjoy_meal_layout(template_key):
        return _to_lodop_layout_enjoy_meal(
            item,
            paper_width_mm=paper_width_mm,
            paper_height_mm=paper_height_mm,
            margin_top_mm=margin_top_mm,
            margin_left_mm=margin_left_mm,
        )

    line_h = 5.0
    for text, scale, bold in _build_lines(item, template_key):
        fs = 14 if scale >= 2 else 10
        row_h = line_h * (1.5 if scale >= 2 else 1.0)
        blocks.append(
            LodopTextBlock(
                x_mm=x,
                y_mm=y,
                text=text,
                font_size_pt=fs,
                bold=bold or scale >= 2,
                width_mm=content_w,
                height_mm=row_h,
            )
        )
        y += row_h
        if y > paper_height_mm - 4:
            break
    return _finalize_lodop_layout(
        LodopLayout(
            paper_width_mm=paper_width_mm,
            paper_height_mm=paper_height_mm,
            margin_top_mm=margin_top_mm,
            margin_left_mm=margin_left_mm,
            blocks=blocks,
        ),
        paper_height_mm=paper_height_mm,
    )


def render_label_payload(
    item: LabelItemIn,
    template_key: str,
    *,
    paper_width_mm: int,
    paper_height_mm: int,
    margin_top_mm: int = 2,
    margin_left_mm: int = 2,
) -> RenderedPrintPayload:
    # 袋贴实物为 75×50：锁定页高，避免沿用面单 130mm 导致一卷打出多张
    if _uses_enjoy_meal_layout(template_key):
        paper_width_mm = ENJOY_MEAL_PAPER_WIDTH_MM
        paper_height_mm = ENJOY_MEAL_PAPER_HEIGHT_MM
        margin_top_mm = 1
        margin_left_mm = 1
    return RenderedPrintPayload(
        feie_xp_content=_to_feie_xp_xml(
            item,
            template_key,
            paper_width_mm=paper_width_mm,
            paper_height_mm=paper_height_mm,
            margin_top_mm=margin_top_mm,
            margin_left_mm=margin_left_mm,
        ),
        yilian_content=_to_yilian_content(item, template_key),
        lodop_layout=_to_lodop_layout(
            item,
            template_key,
            paper_width_mm=paper_width_mm,
            paper_height_mm=paper_height_mm,
            margin_top_mm=margin_top_mm,
            margin_left_mm=margin_left_mm,
        ),
    )


def render_test_label(
    *,
    paper_width_mm: int,
    paper_height_mm: int,
    margin_top_mm: int,
    margin_left_mm: int,
    printer_name: str,
) -> RenderedPrintPayload:
    item = LabelItemIn(
        region="中心医院",
        store_name="OK饭·测试门店",
        address="3号楼502室",
        name="李女士",
        phone_masked="132****6633",
        plan_type="周卡",
        meal_category="午晚餐卡",
        units=1,
        remark="少辣",
        delivery_date="2026-07-29",
        shop_order_id="OKF20260724c69a194b60ca4",
        sf_order_id="SF6504306526672",
        product_title="",
        order_no="ZX001",
        store_pickup=False,
    )
    return render_label_payload(
        item,
        "delivery_meal_full",
        paper_width_mm=paper_width_mm,
        paper_height_mm=paper_height_mm,
        margin_top_mm=margin_top_mm,
        margin_left_mm=margin_left_mm,
    )


def lodop_layout_to_dict(layout: LodopLayout) -> dict[str, Any]:
    return {
        "paper_width_mm": layout.paper_width_mm,
        "paper_height_mm": layout.paper_height_mm,
        "content_height_mm": layout.content_height_mm,
        "margin_top_mm": layout.margin_top_mm,
        "margin_left_mm": layout.margin_left_mm,
        "layout_style": layout.layout_style,
        "header_text": layout.header_text,
        "header_right_text": layout.header_right_text,
        "table_html": layout.table_html,
        "barcodes": [
            {
                "x_mm": b.x_mm,
                "y_mm": b.y_mm,
                "width_mm": b.width_mm,
                "height_mm": b.height_mm,
                "code": b.code,
                "show_text": b.show_text,
                "code_type": b.code_type,
            }
            for b in layout.barcodes
        ],
        "blocks": [
            {
                "x_mm": b.x_mm,
                "y_mm": b.y_mm,
                "text": b.text,
                "font_size_pt": b.font_size_pt,
                "bold": b.bold,
                "width_mm": b.width_mm,
                "height_mm": b.height_mm,
                "align": b.align,
            }
            for b in layout.blocks
        ],
    }
