"""创建配送员：python scripts/create_courier.py C001 123456 张三"""

import argparse
import sys
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.schemas.admin_courier import CourierCreateIn
from app.services.courier_admin_service import create_courier_admin


def main() -> None:
    parser = argparse.ArgumentParser(description="创建配送员账号")
    parser.add_argument("courier_id")
    parser.add_argument("pin")
    parser.add_argument("name", nargs="?", default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        try:
            create_courier_admin(
                db,
                CourierCreateIn(
                    courier_id=args.courier_id,
                    pin=args.pin,
                    name=args.name,
                    is_active=True,
                ),
            )
        except HTTPException as e:
            print(e.detail or "创建失败")
            raise SystemExit(1) from None
        print("创建成功")
    finally:
        db.close()


if __name__ == "__main__":
    main()
