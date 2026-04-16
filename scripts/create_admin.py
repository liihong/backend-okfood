"""创建管理员账号：python scripts/create_admin.py admin your_password"""

import argparse
import sys
from pathlib import Path

# 保证可导入 app（从项目根目录执行）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.admin_user import AdminUser


def main() -> None:
    parser = argparse.ArgumentParser(description="创建后台管理员")
    parser.add_argument("username")
    parser.add_argument("password")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        exists = db.scalar(select(AdminUser).where(AdminUser.username == args.username))
        if exists:
            print("用户名已存在")
            return
        db.add(AdminUser(username=args.username, password_hash=hash_password(args.password)))
        db.commit()
        print("创建成功")
    finally:
        db.close()


if __name__ == "__main__":
    main()
