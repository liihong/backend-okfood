import csv
import os
import re
from datetime import date, datetime

# 与脚本同目录，避免 cwd 不同找不到文件
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, "配送数据 - 4月18日周六.csv")
SQL_OUTPUT = os.path.join(SCRIPT_DIR, "init_data.sql")

# CSV 列序：序号,名称,电话,地址,特殊备注,套餐,开始日期,剩余次数,套餐总次数,续卡时间,...
COL = {
    "name": 1,
    "phone": 2,
    "address": 3,
    "remark": 4,
    "plan": 5,
    "start_date": 6,
    "balance": 7,
    "renew": 9,
}


def parse_friday_leave(col_val: str) -> int:
    """兼容旧表「周五是否配送」：0=周五不送 → is_leaved_tomorrow=1。"""
    if col_val is None or not str(col_val).strip():
        return 0
    try:
        v = int(float(str(col_val).strip()))
    except (TypeError, ValueError):
        return 0
    return 1 if v == 0 else 0


def parse_balance(col_val: str) -> int:
    if col_val is None or not str(col_val).strip():
        return 0
    try:
        return int(float(str(col_val).strip()))
    except (TypeError, ValueError):
        return 0


def parse_start_date_cell(val: str) -> date | None:
    s = (val or "").strip()
    if not s:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def infer_delivery_start(
    start_from_col: date | None,
    remark: str,
    renew_note: str,
) -> date | None:
    """
    配送起始日：默认与「开始日期」列一致；备注中含更晚的「X月Y日开始送」则采用该日。
    """
    if start_from_col is None:
        return None
    year = start_from_col.year
    text = " ".join(
        x.strip()
        for x in (remark or "", renew_note or "")
        if x and str(x).strip()
    )

    patterns = [
        r"(?P<m>\d{1,2})月(?P<d>\d{1,2})日\s*开始",
        r"(?P<m>\d{1,2})月(?P<d>\d{1,2})号\s*开始",
        r"开始\s*[:：]?\s*(?P<m>\d{1,2})[./月](?P<d>\d{1,2})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            mo, dy = int(m.group("m")), int(m.group("d"))
            try:
                return date(year, mo, dy)
            except ValueError:
                continue
    m = re.search(r"(?P<m>\d{1,2})\s*[./]\s*(?P<d>\d{1,2})\s*号?\s*开始", text)
    if m:
        mo, dy = int(m.group("m")), int(m.group("d"))
        try:
            return date(year, mo, dy)
        except ValueError:
            pass
    return start_from_col


def normalize_phone(raw: str, fallback_id: int) -> str:
    s = (raw or "").strip()
    digits = re.sub(r"\D", "", s)
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("1"):
        return digits
    return f"170{fallback_id % 100_000_000:08d}"


def esc(text: str) -> str:
    # 换行会破坏单行 INSERT，统一压成空格
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = " ".join(t.split())
    return t.replace("'", "''")


def dt_sql(d: date) -> str:
    return f"'{d.isoformat()} 00:00:00'"


def cell(row: list[str], idx: int) -> str:
    if idx >= len(row):
        return ""
    return row[idx] if row[idx] is not None else ""


def generate_sql():
    if not os.path.exists(CSV_FILE):
        print(f"错误: 找不到文件 {CSV_FILE}")
        return

    sql_lines = [
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "TRUNCATE TABLE `member_addresses`;",
        "TRUNCATE TABLE `members`;",
        "\n-- ----------------------------",
        "-- 开始初始化数据（created_at 使用表内「开始日期」当日 00:00:00）",
        "-- delivery_start_date：备注中若有更晚「开始送」日期则优先",
        "-- ----------------------------\n",
    ]

    unique_members: dict[str, int] = {}
    member_id_counter = 1
    address_id_counter = 1
    friday_col_idx: int | None = None  # 若表头含「周五是否配送」则解析

    with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header:
            for i, h in enumerate(header):
                if h and "周五是否配送" in h.strip():
                    friday_col_idx = i
                    break
        for row in reader:
            while len(row) < 10:
                row.append("")
            name = cell(row, COL["name"]).strip()
            address = cell(row, COL["address"]).strip()
            if not name or not address:
                continue

            phone_raw = cell(row, COL["phone"]).strip()
            remark_a = cell(row, COL["remark"]).strip()
            renew = cell(row, COL["renew"]).strip()
            parts = [p for p in (remark_a, renew) if p]
            raw_remarks = " | ".join(parts)

            balance = parse_balance(cell(row, COL["balance"]))
            start_d = parse_start_date_cell(cell(row, COL["start_date"]))
            if start_d is None:
                print(f"跳过（无开始日期）: {name}")
                continue

            delivery_start = infer_delivery_start(start_d, remark_a, renew)
            created_sql = dt_sql(start_d)

            plan_raw = cell(row, COL["plan"])
            if "月" in plan_raw:
                plan = "月卡"
            elif "周" in plan_raw:
                plan = "周卡"
            else:
                plan = "次卡"

            if friday_col_idx is not None:
                is_leaved_tomorrow = parse_friday_leave(cell(row, friday_col_idx))
            else:
                is_leaved_tomorrow = 0

            norm_phone = normalize_phone(phone_raw, member_id_counter)

            if norm_phone not in unique_members:
                unique_members[norm_phone] = member_id_counter
                delivery_sql = f"'{delivery_start.isoformat()}'" if delivery_start else "NULL"
                m_sql = (
                    "INSERT INTO `members` (`id`, `phone`, `name`, `wechat_name`, `remarks`, `balance`, "
                    "`plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `created_at`) "
                    f"VALUES ({member_id_counter}, '{esc(norm_phone)}', '{esc(name)}', '{esc(name)}', "
                    f"'{esc(raw_remarks)}', {balance}, '{plan}', 1, {is_leaved_tomorrow}, {delivery_sql}, {created_sql});"
                )
                sql_lines.append(m_sql)
                current_member_id = member_id_counter
                member_id_counter += 1
            else:
                current_member_id = unique_members[norm_phone]

            a_sql = (
                "INSERT INTO `member_addresses` (`id`, `member_id`, `contact_name`, `contact_phone`, `area`, "
                "`area_manual`, `detail_address`, `remarks`, `is_default`, `created_at`, `updated_at`) "
                f"VALUES ({address_id_counter}, {current_member_id}, '{esc(name)}', '{esc(norm_phone)}', "
                f"'市区', 0, '{esc(address)}', '{esc(raw_remarks)}', 1, {created_sql}, {created_sql});"
            )
            sql_lines.append(a_sql)
            address_id_counter += 1

    sql_lines.append("\nSET FOREIGN_KEY_CHECKS = 1;")

    with open(SQL_OUTPUT, "w", encoding="utf8") as f:
        f.write("\n".join(sql_lines))

    print(f"转换完成！已生成 {SQL_OUTPUT}")
    print(f"共处理会员: {member_id_counter - 1} 人，地址: {address_id_counter - 1} 条。")


if __name__ == "__main__":
    generate_sql()
