#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《OKFine 私域配送系统》销售介绍 PDF。文案对着真实界面写，不写功能清单。"""

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import Color, white
from reportlab.lib.utils import ImageReader

SONG = "/System/Library/Fonts/Supplemental/Songti.ttc"
pdfmetrics.registerFont(TTFont("Sans", SONG, subfontIndex=6))
pdfmetrics.registerFont(TTFont("SansB", SONG, subfontIndex=1))

W, H = A4
OUT = "/Users/cwz/project/okfood/app/backend-okfood/docs/sales/OKFine私域配送系统-销售介绍.pdf"
SHOT = "/Users/cwz/project/okfood/app/backend-okfood/docs/sales/screenshots/for-pdf"

INK = Color(0.110, 0.098, 0.090)
MUTED = Color(0.38, 0.35, 0.32)
SOFT = Color(0.55, 0.51, 0.47)
PAPER = Color(0.957, 0.945, 0.922)
CARD = Color(0.992, 0.984, 0.973)
ACCENT = Color(0.761, 0.255, 0.047)
LINE = Color(0.878, 0.855, 0.816)

NO_START = set("，。、；：！？）」』】》…·")
NO_END = set("（「『【《")


def _flush_chars(text, font, size, width):
    lines, buf, i = [], "", 0
    chars = list(text)
    while i < len(chars):
        ch = chars[i]
        trial = buf + ch
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            buf = trial
            i += 1
            continue
        if ch in NO_START and len(buf) > 1:
            lines.append(buf[:-1])
            buf = buf[-1] + ch
            i += 1
            continue
        if buf and buf[-1] in NO_END and len(buf) > 1:
            lines.append(buf[:-1])
            buf = buf[-1]
            continue
        if buf:
            lines.append(buf)
        buf = ch
        i += 1
    if buf:
        lines.append(buf)
    return lines


def wrap(text, font, size, width):
    lines = []
    for para in text.split("\n"):
        if para == "":
            lines.append("")
            continue
        clauses, buf = [], ""
        for ch in para:
            buf += ch
            if ch in "，。、；":
                clauses.append(buf)
                buf = ""
        if buf:
            clauses.append(buf)
        line = ""
        for part in clauses:
            if line and pdfmetrics.stringWidth(line + part, font, size) <= width:
                line += part
                continue
            if line:
                lines.append(line)
                line = ""
            if pdfmetrics.stringWidth(part, font, size) <= width:
                line = part
            else:
                broken = _flush_chars(part, font, size, width)
                lines.extend(broken[:-1])
                line = broken[-1]
        if line:
            lines.append(line)
    return lines


def draw_bg(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def wordmark(c):
    c.setFillColor(ACCENT)
    c.circle(48, H - 52, 4.2, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("SansB", 11)
    c.drawString(60, H - 56, "OKFine")
    c.setFillColor(SOFT)
    c.setFont("Sans", 11)
    c.drawString(108, H - 56, "私域配送系统")


def footer(c, page, total=4):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.line(48, 36, W - 48, 36)
    c.setFillColor(SOFT)
    c.setFont("Sans", 8.5)
    c.drawString(48, 22, "真实店面。姓名、电话、地址做了遮挡。")
    c.drawRightString(W - 48, 22, f"{page}  /  {total}")


def draw_lines(c, lines, x, y, font, size, color, leading):
    c.setFillColor(color)
    c.setFont(font, size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def text_block(c, text, x, y, width, font="Sans", size=12, color=MUTED, leading=20):
    return draw_lines(c, wrap(text, font, size, width), x, y, font, size, color, leading)


def rounded_image(c, path, x, y_top, max_w, max_h, radius=8):
    """按比例放下图片，上沿对齐 y_top，返回下沿。"""
    iw, ih = ImageReader(path).getSize()
    scale = min(max_w / float(iw), max_h / float(ih))
    w, h = iw * scale, ih * scale
    y = y_top - h
    c.saveState()
    clip = c.beginPath()
    clip.roundRect(x, y, w, h, radius)
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(path, x, y, w, h, mask="auto")
    c.restoreState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, radius, fill=0, stroke=1)
    return y, w


def page_one(c):
    draw_bg(c)
    wordmark(c)
    y = H - 108
    c.setFillColor(INK)
    c.setFont("SansB", 26)
    c.drawString(48, y, "早上先看今天做几份。")
    y -= 36
    body = (
        "飞书上能记，但得你自己数。谁请假了，谁改成自己来取，谁临时加一份，消息还在微信里。\n"
        "你一边备菜一边翻，很容易数错。多做浪费，少做就得补。"
    )
    y = text_block(c, body, 48, y, W - 96, size=12.5, leading=21)
    y -= 8
    c.setFillColor(INK)
    c.setFont("Sans", 12.5)
    c.drawString(48, y, "现在打开电脑，就是这一页。")
    y -= 16
    bottom, _ = rounded_image(c, f"{SHOT}/dash.jpg", 48, y, W - 96, 340)
    y = bottom - 22
    cap = "图上这个 102，就是当天午餐要出的份数。请假、自提、单次加的，在下面分开。后厨按这个数做，不用再拿计算器加总。"
    text_block(c, cap, 48, y, W - 96, size=12, color=INK, leading=20)
    footer(c, 1)
    c.showPage()


def page_two(c):
    draw_bg(c)
    wordmark(c)
    y = H - 108
    c.setFillColor(INK)
    c.setFont("SansB", 26)
    c.drawString(48, y, "顾客在微信里自己弄。")
    y -= 32
    lead = "不用再发消息给你。你在备货、在做的时候，也不用停下来改表。"
    y = text_block(c, lead, 48, y, W - 96, size=12.5, leading=21)
    y -= 10
    gap = 14
    col_w = (W - 96 - gap) / 2
    left_bottom, left_w = rounded_image(c, f"{SHOT}/mini-home.png", 48, y, col_w, 300)
    right_bottom, _ = rounded_image(c, f"{SHOT}/mini-menu.png", 48 + col_w + gap, y, col_w, 300)
    cap_y = min(left_bottom, right_bottom) - 18
    c.setFillColor(SOFT)
    c.setFont("Sans", 10)
    c.drawString(48, cap_y, "小程序首页。卡和今天的活动。")
    c.drawString(48 + col_w + gap, cap_y, "点单。这周每天吃什么、多少钱。")
    y = cap_y - 28
    body = (
        "左边是他一打开看到的：周卡、月卡，几次、多少钱。\n"
        "右边是本周菜单。午餐、晚餐分开，这天的菜和价格写在上面。\n"
        "请假、改地址、看还剩几顿，也在这个小程序里。他提交完，你那边的表自己变。"
    )
    text_block(c, body, 48, y, W - 96, size=12.5, color=INK, leading=21)
    footer(c, 2)
    c.showPage()


def page_three(c):
    draw_bg(c)
    wordmark(c)
    y = H - 108
    c.setFillColor(INK)
    c.setFont("SansB", 26)
    c.drawString(48, y, "这张表，就是你现在的飞书。")
    y -= 32
    lead = "差别在于：飞书每一行都得你亲手改。这里顾客改完，行自己变。"
    y = text_block(c, lead, 48, y, W - 96, size=12.5, leading=21)
    y -= 12
    bottom, _ = rounded_image(c, f"{SHOT}/members.jpg", 48, y, W - 96, 360)
    y = bottom - 22
    cap = (
        "看右边「剩余/总次数」。2/6 就是用掉 4 次、还剩 2 次。该续的，状态写成待续费。\n"
        "以前顾客说一声明天不吃，你得在飞书里找到他那一行。忙的时候忘了，第二天照样送，次数还扣了。"
    )
    text_block(c, cap, 48, y, W - 96, size=12, color=INK, leading=20)
    footer(c, 3)
    c.showPage()


def page_four(c):
    draw_bg(c)
    wordmark(c)
    y = H - 100
    c.setFillColor(INK)
    c.setFont("SansB", 24)
    c.drawString(48, y, "钱不用记两笔。")
    y -= 28
    lead = "小程序里付的，还有你登记的微信转账，进的是同一页。飞书是转账记一笔，线上再记一笔，月底才对。"
    y = text_block(c, lead, 48, y, W - 96, size=12, leading=20)
    y -= 10
    bottom, _ = rounded_image(c, f"{SHOT}/finance.jpg", 48, y, W - 96, 250)
    y = bottom - 20
    cap = "这一天收了 20 笔，这个月 572 笔。周卡、月卡、单次，下面分得开。金额在图上遮住了，结构就是这样。"
    y = text_block(c, cap, 48, y, W - 96, size=12, color=INK, leading=20)

    c.setFillColor(ACCENT)
    c.roundRect(48, 52, W - 96, 86, 10, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("SansB", 15)
    c.drawString(66, 110, "把你现在的记法发我")
    cta = "飞书表格，或者微信里那一堆请假消息，拍一张就行。我按你的单子对一下，看这张表能不能换掉。"
    text_block(c, cta, 66, 90, W - 148, size=11, color=Color(1, 0.94, 0.90), leading=16)
    c.showPage()


def main():
    c = canvas.Canvas(OUT, pagesize=A4)
    c.setTitle("OKFine 私域配送系统")
    c.setAuthor("火源网络科技")
    page_one(c)
    page_two(c)
    page_three(c)
    page_four(c)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
