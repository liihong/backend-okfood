#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动截取管理后台页面截图，保存到 docs/sales/screenshots/。

前置条件：
  1. 后端 API 已启动（默认 http://127.0.0.1:8001）
  2. 管理端 dev 已启动（默认 http://127.0.0.1:5173）
  3. pip install playwright && playwright install chromium

用法：
  python scripts/capture_admin_screenshots.py
  python scripts/capture_admin_screenshots.py --admin-url http://127.0.0.1:5173 --api-url http://127.0.0.1:8001
  ADMIN_USER=admin ADMIN_PASS=你的密码 python scripts/capture_admin_screenshots.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "sales" / "screenshots"

# 管理后台路由 → 输出文件名（与 manifest.json 中 admin-* 对应）
ADMIN_PAGES: list[tuple[str, str, str]] = [
    ("admin-dashboard.png", "/dashboard", "营业概览"),
    ("admin-members.png", "/users", "会员档案库"),
    ("admin-card-orders.png", "/card-orders", "开卡工单"),
    ("admin-orders.png", "/orders", "订单管理"),
    ("admin-delivery.png", "/delivery", "智能配送大表"),
    ("admin-finance.png", "/finance", "财务中心"),
    ("admin-weekly-menu.png", "/weekly-menu", "本周菜单"),
    ("admin-marketing-banners.png", "/marketing/home-banners", "首页 Banner"),
]


def login(api_url: str, username: str, password: str) -> str:
    resp = httpx.post(
        f"{api_url.rstrip('/')}/api/admin/login",
        json={"username": username, "password": password},
        timeout=15.0,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise RuntimeError(f"登录失败: {body.get('msg')}")
    token = (body.get("data") or {}).get("access_token")
    if not token:
        raise RuntimeError("登录响应缺少 access_token")
    return token


def capture(admin_url: str, api_url: str, username: str, password: str) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("请先安装: pip install playwright && playwright install chromium")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    token = login(api_url, username, password)
    print(f"登录成功，开始截取 {len(ADMIN_PAGES)} 个管理后台页面…")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
        )
        page = context.new_page()

        # 先打开管理端域名，再写入 token（与 okfood-admin localStorage 键一致）
        page.goto(f"{admin_url.rstrip('/')}/login", wait_until="domcontentloaded")
        page.evaluate(
            """([token]) => {
                localStorage.setItem('okfood_admin_access_token', token);
                localStorage.setItem('okfood_admin_kind', 'full');
            }""",
            [token],
        )

        ok, fail = 0, 0
        for filename, route, title in ADMIN_PAGES:
            out_path = OUT_DIR / filename
            url = f"{admin_url.rstrip('/')}{route}"
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(1.2)  # 等待图表/地图渲染
                page.screenshot(path=str(out_path), full_page=True)
                print(f"  [OK] {title} -> {filename}")
                ok += 1
            except Exception as e:
                print(f"  [FAIL] {title} ({url}): {e}")
                fail += 1

        browser.close()

    print(f"\n完成：成功 {ok} 张，失败 {fail} 张，目录: {OUT_DIR.resolve()}")
    if ok:
        print("请重新运行: python scripts/generate_product_full_docx.py")


def main():
    parser = argparse.ArgumentParser(description="自动截取 OK饭 管理后台截图")
    parser.add_argument("--admin-url", default=os.getenv("ADMIN_URL", "http://127.0.0.1:5173"))
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--user", default=os.getenv("ADMIN_USER", "admin"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASS", "admin123"))
    args = parser.parse_args()
    capture(args.admin_url, args.api_url, args.user, args.password)


if __name__ == "__main__":
    main()
