"""导入与路由冒烟：无需真实 MySQL（不连库）。"""

from __future__ import annotations


def test_import_app():
    from app.main import app

    assert app is not None
    paths = {r.path for r in app.router.routes if hasattr(r, "path")}
    assert any("/api/user" in p for p in paths)
