"""
【已废弃】原用于从 `detail_address` 启发式回填 `map_location_text` / `door_detail`。

当前库表已移除 `detail_address` 与省市区独立列；相关变更请通过 `sql/migrations`
手动迁移并在回填后再删列。请勿再运行本脚本；保留文件仅为说明历史迁移路径。
"""

from __future__ import annotations


def main() -> int:
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
