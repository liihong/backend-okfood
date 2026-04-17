import pandas as pd
import os

# 配置信息
CSV_FILE = '配送数据 - 4月18日周六.csv'  # 你的文件名
SQL_OUTPUT = 'init_data.sql'

def generate_sql():
    if not os.path.exists(CSV_FILE):
        print(f"错误: 找不到文件 {CSV_FILE}")
        return

    # 读取CSV，过滤掉没有名称或地址的行（比如那些方向指示行）
    df = pd.read_csv(CSV_FILE)
    df_clean = df[df['名称'].notna() & df['地址'].notna()].copy()

    sql_lines = [
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "TRUNCATE TABLE `member_addresses`;",
        "TRUNCATE TABLE `members`;",
        "\n-- ----------------------------",
        "-- 开始初始化数据",
        "-- ----------------------------\n"
    ]

    unique_members = {} # 记录手机号对应的会员ID
    member_id_counter = 1
    address_id_counter = 1

    def parse_friday_leave(col_val):
        """0=周五不送(请假)，非 0（含 1、2）= 周五送。列类型常为 float，不能 str == '1'。"""
        if pd.isna(col_val):
            return 1
        try:
            v = int(float(col_val))
        except (TypeError, ValueError):
            return 1
        return 1 if v == 0 else 0

    def parse_balance(col_val):
        """剩余次数列多为 float，不能用 str.isdigit()。"""
        if pd.isna(col_val):
            return 0
        try:
            return int(float(col_val))
        except (TypeError, ValueError):
            return 0

    for _, row in df_clean.iterrows():
        name = str(row['名称']).strip()
        phone = str(row['电话']).strip()
        address = str(row['地址']).strip()
        raw_remarks = str(row['特殊备注']).strip() if pd.notnull(row['特殊备注']) else ''
        balance = parse_balance(row['剩余次数'])
        
        # 套餐映射
        plan_raw = str(row['套餐'])
        if '月' in plan_raw: plan = '月卡'
        elif '周' in plan_raw: plan = '周卡'
        else: plan = '次卡'

        is_leaved_tomorrow = parse_friday_leave(row['周五是否配送'])

        # SQL 转义处理
        def esc(text):
            return text.replace("'", "''")

        # 处理会员（如果电话重复，视为同一会员的多个地址）
        if phone not in unique_members:
            unique_members[phone] = member_id_counter
            m_sql = (f"INSERT INTO `members` (`id`, `phone`, `name`, `wechat_name`, `remarks`, `balance`, `plan_type`, `is_active`, `is_leaved_tomorrow`) "
                     f"VALUES ({member_id_counter}, '{esc(phone)}', '{esc(name)}', '{esc(name)}', '{esc(raw_remarks)}', {balance}, '{plan}', 1, {is_leaved_tomorrow});")
            sql_lines.append(m_sql)
            current_member_id = member_id_counter
            member_id_counter += 1
        else:
            current_member_id = unique_members[phone]

        # 处理地址
        a_sql = (f"INSERT INTO `member_addresses` (`id`, `member_id`, `contact_name`, `contact_phone`, `area`, `detail_address`, `remarks`, `is_default`) "
                 f"VALUES ({address_id_counter}, {current_member_id}, '{esc(name)}', '{esc(phone)}', '市区', '{esc(address)}', '{esc(raw_remarks)}', 1);")
        sql_lines.append(a_sql)
        address_id_counter += 1

    sql_lines.append("\nSET FOREIGN_KEY_CHECKS = 1;")

    # 写入文件
    with open(SQL_OUTPUT, 'w', encoding='utf8') as f:
        f.write("\n".join(sql_lines))
    
    print(f"转换完成！已生成 {SQL_OUTPUT}")
    print(f"共处理会员: {member_id_counter - 1} 人，地址: {address_id_counter - 1} 条。")

if __name__ == "__main__":
    generate_sql()