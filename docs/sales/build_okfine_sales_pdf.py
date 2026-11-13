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


def footer(c, page, total=5):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.line(48, 36, W - 48, 36)
    c.setFillColor(SOFT)
    c.setFont("Sans", 8.5)
    c.drawString(48, 22, "一家正在用的店。姓名、电话、地址做了遮挡。")
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
    y = H - 102
    c.setFillColor(INK)
    c.setFont("SansB", 26)
    c.drawString(48, y, "早上打开，先看今天做几份。")
    y -= 32
    body = "以前这个数要自己加。谁请假、谁改成自己来取、谁临时加一份，消息都在微信里。你一边备菜一边翻，很容易加错。"
    y = text_block(c, body, 48, y, W - 96, size=12.5, leading=21)
    y -= 8
    c.setFillColor(INK)
    c.setFont("Sans", 12.5)
    c.drawString(48, y, "现在打开电脑，就是这一页。")
    y -= 14
    bottom, _ = rounded_image(c, f"{SHOT}/dash-today.jpg", 48, y, W - 96, 390)
    y = bottom - 18
    cap = "今天午餐 129 份，晚餐 12 份。明天午餐 150，晚餐 17。上面是菜，下面是后厨这三天的数。后厨按这个做。"
    text_block(c, cap, 48, y, W - 96, size=12.5, color=INK, leading=21)
    footer(c, 1)
    c.showPage()


def page_feishu(c):
    draw_bg(c)
    wordmark(c)
    y = H - 96
    c.setFillColor(INK)
    c.setFont("SansB", 24)
    c.drawString(48, y, "你现在的飞书，就是这几张表。")
    y -= 28
    lead = "一行一个人。电话、地址、周卡还是月卡、还剩几次，全靠手改。黄的那几行是该续卡了，得你自己看出来。"
    y = text_block(c, lead, 48, y, W - 96, size=12.5, leading=20)
    y -= 8
    for name in ("feishu-1.jpg", "feishu-2.jpg", "feishu-3.jpg"):
        bottom, _ = rounded_image(c, f"{SHOT}/{name}", 48, y, W - 96, 168)
        y = bottom - 8
    y -= 6
    text_block(c, "姓名、电话、地址打过码。表还是原来那张。", 48, y, W - 96, size=12, color=INK, leading=18)
    footer(c, 2)
    c.showPage()


def page_two(c):
    draw_bg(c)
    wordmark(c)
    y = H - 102
    c.setFillColor(INK)
    c.setFont("SansB", 26)
    c.drawString(48, y, "买卡、看菜单，都在微信里。")
    y -= 30
    lead = "他不用再发消息问你。几次、多少钱、这周吃什么，打开就能看见。"
    y = text_block(c, lead, 48, y, W - 96, size=12.5, leading=21)
    y -= 12
    gap = 18
    col_w = (W - 96 - gap) / 2
    left_bottom, _ = rounded_image(c, f"{SHOT}/mini-home.png", 48, y, col_w, 320)
    right_x = 48 + col_w + gap
    right_bottom, _ = rounded_image(c, f"{SHOT}/mini-menu.png", right_x, y, col_w, 320)
    cap_y = min(left_bottom, right_bottom) - 16
    c.setFillColor(SOFT)
    c.setFont("Sans", 11)
    c.drawString(48, cap_y, "卡。周卡、月卡，几次、多少钱。")
    c.drawString(right_x, cap_y, "菜单。这周的菜，午餐和晚餐分开。")
    y = cap_y - 28
    body = "请假、改地址，也在这个微信里。他弄完，你电脑上那张表自己变。下一页就是请假那一下。"
    text_block(c, body, 48, y, W - 96, size=12.5, color=INK, leading=21)
    footer(c, 3)
    c.showPage()


def page_three(c):
    draw_bg(c)
    wordmark(c)
    y = H - 102
    c.setFillColor(INK)
    c.setFont("SansB", 26)
    c.drawString(48, y, "明天不吃，点一下就行。")
    y -= 28
    lead = "以前他在微信里说一声。你在备菜，消息就沉了。第二天照样送，次数还扣了。"
    y = text_block(c, lead, 48, y, W - 96, size=12.5, leading=21)
    y -= 14
    img_w = 300
    img_x = 48
    img_bottom, _ = rounded_image(c, f"{SHOT}/mini-leave.png", img_x, y, img_w, 340)
    text_x = img_x + img_w + 28
    text_w = W - 48 - text_x
    ty = y - 36
    c.setFillColor(INK)
    c.setFont("SansB", 16)
    c.drawString(text_x, ty, "就是这个红框。")
    ty -= 32
    note = "他点一下，明天就不送，这一顿不扣。你不用停下来回微信，也不用再去飞书里改那一行。"
    ty = text_block(c, note, text_x, ty, text_w, size=13, color=INK, leading=22)
    ty -= 10
    more = "要请好几天，比如出差、出去玩，往下拉就是。"
    text_block(c, more, text_x, ty, text_w, size=13, color=MUTED, leading=22)
    y = img_bottom - 36
    c.setFillColor(INK)
    c.setFont("SansB", 16)
    c.drawString(48, y, "你人还在做货。表已经改完了。")
    footer(c, 4)
    c.showPage()


def page_four(c):
    draw_bg(c)
    wordmark(c)
    y = H - 96
    c.setFillColor(INK)
    c.setFont("SansB", 24)
    c.drawString(48, y, "今天送谁，看这一张。")
    y -= 26
    lead = "飞书里那一堆行，换成这一张。他在微信里请假、改地址之后，这一行自己变，不用你改。"
    y = text_block(c, lead, 48, y, W - 96, size=12, leading=19)
    y -= 10
    bottom, _ = rounded_image(c, f"{SHOT}/delivery.jpg", 48, y, W - 96, 300)
    y = bottom - 16
    cap = "108 是这一顿要送的份。上面按片区分开。每一行是一个地址：几份、送到哪、电话、备注。人名和电话打了码。送到了，右边标一下。"
    y = text_block(c, cap, 48, y, W - 96, size=12, color=INK, leading=19)
    y -= 8
    money = "钱也在电脑上。小程序里付的，还有你登记的微信转账，进同一页，不用记两笔。"
    y = text_block(c, money, 48, y, W - 96, size=12, color=MUTED, leading=19)

    c.setFillColor(ACCENT)
    c.roundRect(48, 50, W - 96, 72, 10, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("SansB", 14)
    c.drawString(66, 92, "把你现在的飞书拍一张发我")
    cta = "我拿你的单子对一下，看这张表能不能换掉。"
    text_block(c, cta, 66, 72, W - 148, size=11.5, color=Color(1, 0.94, 0.90), leading=16)
    footer(c, 5)
    c.showPage()


def main():
    c = canvas.Canvas(OUT, pagesize=A4)
    c.setTitle("OKFine 私域配送系统")
    c.setAuthor("火源网络科技")
    page_one(c)
    page_feishu(c)
    page_two(c)
    page_three(c)
    page_four(c)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
