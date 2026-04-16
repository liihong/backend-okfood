-- 会员批量导入（根据2025-04-15 提供清单生成）
-- 执行前请确认目标库已是 sql/schema.sql 中的 members 结构（无 address/lng/lat/area 列）。
-- 说明：
--   1) members 主键为自增 id，phone 唯一；同号多地址已拆成带后缀手机号的占位键（见各条 remarks），请上线前改为真实可登录号码或合并业务数据。
--   2) 「慧子」「世青小学」原表无可用手机号，使用19900010001、19900010002 占位，务必人工替换。
--   3) balance 一律0，套餐次数请后续在管理端充值或改表。
--   4) 详细地址与片区写入 member_addresses 默认地址；lng/lat 为空，可后续用管理端改地址触发地理编码。

SET NAMES utf8mb4;

INSERT INTO `members` (
  `phone`,
  `name`,
  `remarks`,
  `balance`,
  `plan_type`,
  `is_active`,
  `is_leaved_tomorrow`,
  `leave_range_start`,
  `leave_range_end`,
  `last_low_balance_notify_date`
) VALUES
('13503804580', '苗苗', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15225982983', '崔菲菲', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15225935226', '郝郝', '2周卡/4月15续了一周的卡', 0, '周卡', 1, 0, NULL, NULL, NULL),
('15516527581', '宋雨薇', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15137335868', '程芳', '周二开始配送；周六不送', 0, '周卡', 1, 0, NULL, NULL, NULL),
('13683738639', '杨蓉', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('19900010001', '慧子', '【无手机号待补】原表为「无」', 0, '周卡', 1, 0, NULL, NULL, NULL),
('15286910838', '张女士', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15736990666', '焦磊', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18611288062', '赵火火', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13523252957', '魏女士', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13789073701', '天天', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('19121270632', '李卓儒', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18637352697', '中中', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13839065606', '市政府', '需要加热', 0, '周卡', 1, 0, NULL, NULL, NULL),
('15690796622', '姚帅星', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13837375666', '申奥', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13072662392', '方悦', NULL, 0, NULL, 1, 0, NULL, NULL, NULL),
('13503735127', '樊肖捷', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15903875314', '羊', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18439082533', '靳豆豆', '周4，周5，周6请假', 0, '周卡', 1, 0, NULL, NULL, NULL),
('19337380888', '周周', NULL, 0, '月卡', 1, 0, NULL, NULL, NULL),
('13273714230', '马晓楠', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18238778808', '梅子', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18532297750', '李嘉伟', '不要芝麻', 0, '月卡', 1, 0, NULL, NULL, NULL),
('16637365665', '云上', NULL, 0, '周卡', 0, 0, NULL, NULL, NULL),
('18837338833', '成光泽', '外卖放到七号楼二单元东边电梯拍照就行了', 0, '周卡', 1, 0, NULL, NULL, NULL),
('13839055526', '李海玲', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('17371250315', '一只三文鱼', '不要洋葱葱姜蒜', 0, '周卡', 1, 0, NULL, NULL, NULL),
('15603739778', '路路', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('16627755424', '泡泡', '不打电话', 0, '月卡', 1, 0, NULL, NULL, NULL),
('13598680803', '韩啊园', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13837399234', '舞魅', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15637399816', '洋洋', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13460245124', '孟女士', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13781939428', '白玉', NULL, 0, '月卡', 1, 0, NULL, NULL, NULL),
('15736969016', '于悦', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15565722060', '洋洋', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13837369696', '陈女士', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13072666882', '李女士', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('13837343744', '赵琰', '赠个小蛋糕', 0, '周卡', 1, 0, NULL, NULL, NULL),
('18695922228', '33', NULL, 0, '月卡', 1, 0, NULL, NULL, NULL),
('18337311022', '王晓庆', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18737306642', '文女士', NULL, 0, '月卡', 1, 0, NULL, NULL, NULL),
('13303733442', '贾瑞', '别打电话，放门口', 0, '周卡', 1, 0, NULL, NULL, NULL),
('13653907075', '王晴', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18638315659', '张云1', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18638315659B', '张云2', '【同机主18638315659】第二条配送地址', 0, '周卡', 1, 0, NULL, NULL, NULL),
('18236141334', '刘思雨', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18337325613', '李瑞', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18790785678', '李琛', '11点50送', 0, '周卡', 1, 0, NULL, NULL, NULL),
('13103737399', '高力', NULL, 0, '月卡', 1, 0, NULL, NULL, NULL),
('13323738251', '牛菁菁', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('1590305000', '张媛媛', '【原表电话10位1590305000，请核对是否缺位】', 0, '周卡', 1, 0, NULL, NULL, NULL),
('15136760777', '李洋1', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15136760777B', '李洋2', '【同机主15136760777】第二条配送地址', 0, '周卡', 1, 0, NULL, NULL, NULL),
('15137386331', '柠檬糖', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18637308802', '张女士', '周六不送', 0, '月卡', 1, 0, NULL, NULL, NULL),
('15036611288', '张萍', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('18530710880', '珍珠', '周一~周五送；周六不送', 0, '周卡', 1, 0, NULL, NULL, NULL),
('17630171678', '弓长', NULL, 0, '周卡', 1, 0, NULL, NULL, NULL),
('15736986665', '冯苗', '陈处理', 0, '次卡', 1, 0, NULL, NULL, NULL),
('19900010002', '世青小学', '【无可用手机号】原表电话列：这个放店里，店里人去送；陈处理', 0, '次卡', 1, 0, NULL, NULL, NULL),
('13598660312', '静静', '陈处理', 0, '周卡', 1, 0, NULL, NULL, NULL);

INSERT INTO `member_addresses` (
  `member_id`,
  `contact_name`,
  `contact_phone`,
  `area`,
  `detail_address`,
  `remarks`,
  `lng`,
  `lat`,
  `is_default`
)
SELECT m.`id`, v.`contact_name`, v.`contact_phone`, v.`area`, v.`detail_address`, v.`remarks`, v.`lng`, v.`lat`, v.`is_default`
FROM `members` m
INNER JOIN (
  SELECT '13503804580' AS phone, '苗苗' AS contact_name, '13503804580' AS contact_phone, '东区' AS area, '宝龙龙邸 4号楼1单元1202' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15225982983' AS phone, '崔菲菲' AS contact_name, '15225982983' AS contact_phone, '东区' AS area, '宝龙国际社区6号楼2单元30楼3005' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15225935226' AS phone, '郝郝' AS contact_name, '15225935226' AS contact_phone, '东区' AS area, '枫景上东-6号楼2单元2105' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15516527581' AS phone, '宋雨薇' AS contact_name, '15516527581' AS contact_phone, '东区' AS area, '枫景上东-11号楼2单元404' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15137335868' AS phone, '程芳' AS contact_name, '15137335868' AS contact_phone, '东区' AS area, '红旗区向阳路松江帕提欧小区7号楼2单元1101' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13683738639' AS phone, '杨蓉' AS contact_name, '13683738639' AS contact_phone, '东区' AS area, '新乡医学院南校区-南门口 打电话' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '19900010001' AS phone, '慧子' AS contact_name, '19900010001' AS contact_phone, '东区' AS area, '诚城紫钰北区-52号楼2单元 2202' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15286910838' AS phone, '张女士' AS contact_name, '15286910838' AS contact_phone, '东区' AS area, '诚诚紫钰北区-58号楼2单元 302' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15736990666' AS phone, '焦磊' AS contact_name, '15736990666' AS contact_phone, '东区' AS area, '碧桂园时代城-6号楼5楼502室' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18611288062' AS phone, '赵火火' AS contact_name, '18611288062' AS contact_phone, '东区' AS area, '荷塘月色假日酒店-20楼2012' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13523252957' AS phone, '魏女士' AS contact_name, '13523252957' AS contact_phone, '东区' AS area, '平原路与新五街交叉口-公村社区13号楼1单元1401' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13789073701' AS phone, '天天' AS contact_name, '13789073701' AS contact_phone, '东区' AS area, '跨境贸易大厦(可以放大厅前台)' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '19121270632' AS phone, '李卓儒' AS contact_name, '19121270632' AS contact_phone, '东区' AS area, '靖业公元国际 30楼-不从米诺斯上/从西边电梯上30楼' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18637352697' AS phone, '中中' AS contact_name, '18637352697' AS contact_phone, '东区' AS area, '嘉亿互联网大厦二楼 前台' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13839065606' AS phone, '市政府' AS contact_name, '13839065606' AS contact_phone, '东区' AS area, '市政府门口传达室，拍照发群' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15690796622' AS phone, '姚帅星' AS contact_name, '15690796622' AS contact_phone, '东区' AS area, '伟业中央公园16号楼2单元1901' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13837375666' AS phone, '申奥' AS contact_name, '13837375666' AS contact_phone, '东区' AS area, '和谐城小区-9号楼2单元801' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13072662392' AS phone, '方悦' AS contact_name, '13072662392' AS contact_phone, '东区' AS area, '牧野区逸品紫晶2号楼3单元703' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13503735127' AS phone, '樊肖捷' AS contact_name, '13503735127' AS contact_phone, '东区' AS area, '阳光365小区-5号楼一单元701' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15903875314' AS phone, '羊' AS contact_name, '15903875314' AS contact_phone, '东区' AS area, '康桥美庭-4号楼二单元二楼东' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18439082533' AS phone, '靳豆豆' AS contact_name, '18439082533' AS contact_phone, '东区' AS area, '盛大凯旋城西门13号楼1205' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '19337380888' AS phone, '周周' AS contact_name, '19337380888' AS contact_phone, '东区' AS area, '正商城二期 19号楼2302' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13273714230' AS phone, '马晓楠' AS contact_name, '13273714230' AS contact_phone, '东区' AS area, '大桥云锦府19号楼1单元2201' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18238778808' AS phone, '梅子' AS contact_name, '18238778808' AS contact_phone, '东区' AS area, '大桥云锦府3 号楼2单元902' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18532297750' AS phone, '李嘉伟' AS contact_name, '18532297750' AS contact_phone, '北边' AS area, '牧野区荣校路-龙湖景庭-2号楼1单元605放到门口水桶上' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '16637365665' AS phone, '云上' AS contact_name, '16637365665' AS contact_phone, '北边' AS area, '中建海德壹号9号楼1单元809' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18837338833' AS phone, '成光泽' AS contact_name, '18837338833' AS contact_phone, '北边' AS area, '牧野区-金辰国际-7号楼2单元东电梯1701' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13839055526' AS phone, '李海玲' AS contact_name, '13839055526' AS contact_phone, '北边' AS area, '金辰国际6号楼三单元' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '17371250315' AS phone, '一只三文鱼' AS contact_name, '17371250315' AS contact_phone, '北边' AS area, '牧野区-二十二所第一生活区-2号楼1单元3楼西' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15603739778' AS phone, '路路' AS contact_name, '15603739778' AS contact_phone, '北边' AS area, '郊委路-太阳城一期-3号楼201-放家门口' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '16627755424' AS phone, '泡泡' AS contact_name, '16627755424' AS contact_phone, '北边' AS area, '都市名城1号楼1单元11楼1106' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13598680803' AS phone, '韩啊园' AS contact_name, '13598680803' AS contact_phone, '北边' AS area, '北辰悦府-1号楼2单元10楼1001门口有个凳子' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13837399234' AS phone, '舞魅' AS contact_name, '13837399234' AS contact_phone, '北边' AS area, '精神病院家属院24号楼2单元6楼西户' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15637399816' AS phone, '洋洋' AS contact_name, '15637399816' AS contact_phone, '北边' AS area, '豫飞·金色城邦7号楼3004' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13460245124' AS phone, '孟女士' AS contact_name, '13460245124' AS contact_phone, '北边' AS area, '绿营花园第1期-5号楼-部队东门小窗台' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13781939428' AS phone, '白玉' AS contact_name, '13781939428' AS contact_phone, '北边' AS area, '牧野区-河师大家属院-20号楼6单元3楼西户' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15736969016' AS phone, '于悦' AS contact_name, '15736969016' AS contact_phone, '北边' AS area, '牧野区-河师大家属院-27号楼2单元402' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15565722060' AS phone, '洋洋' AS contact_name, '15565722060' AS contact_phone, '北边' AS area, '新二街牧野花园西门38-2-1102' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13837369696' AS phone, '陈女士' AS contact_name, '13837369696' AS contact_phone, '南边' AS area, '向阳路与牧野路交叉口-红旗小区北区-2号楼2单元3楼东' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13072666882' AS phone, '李女士' AS contact_name, '13072666882' AS contact_phone, '南边' AS area, '新飞大道与友谊路交叉口-中国平安财产保险股份有限公司' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13837343744' AS phone, '赵琰' AS contact_name, '13837343744' AS contact_phone, '南边' AS area, '国悦城悦府壹号院4号楼一单元602' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18695922228' AS phone, '33' AS contact_name, '18695922228' AS contact_phone, '南边' AS area, '大桥悦时代门口/快到跟打电话' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18337311022' AS phone, '王晓庆' AS contact_name, '18337311022' AS contact_phone, '南边' AS area, '高新区政府行政服务中心-华兰大道470号' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18737306642' AS phone, '文女士' AS contact_name, '18737306642' AS contact_phone, '南边' AS area, '火电厂家属院3号楼2单元1楼东户' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13303733442' AS phone, '贾瑞' AS contact_name, '13303733442' AS contact_phone, '南边' AS area, '和平路纺织路交叉口隆基新谊城8号楼4单元1501' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13653907075' AS phone, '王晴' AS contact_name, '13653907075' AS contact_phone, '南边' AS area, '光彩大市场南面过河，道河世家小区，银行' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18638315659' AS phone, '张云1' AS contact_name, '18638315659' AS contact_phone, '南边' AS area, '新飞大道道清路新乡融诚信息咨询中心前台' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18638315659B' AS phone, '张云2' AS contact_name, '18638315659B' AS contact_phone, '南边' AS area, '新飞大道道清路新乡融诚信息咨询中心前台' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18236141334' AS phone, '刘思雨' AS contact_name, '18236141334' AS contact_phone, '南边' AS area, '道清路-温泉花园小区-696号' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18337325613' AS phone, '李瑞' AS contact_name, '18337325613' AS contact_phone, '南边' AS area, '道清路-青青家园-7号楼-西单元-4楼西户' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18790785678' AS phone, '李琛' AS contact_name, '18790785678' AS contact_phone, '西边' AS area, '忆通壹世界从南门进2号楼2单元2902' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13103737399' AS phone, '高力' AS contact_name, '13103737399' AS contact_phone, '西边' AS area, '忆通壹世界从北门进19号楼1单元1502' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13323738251' AS phone, '牛菁菁' AS contact_name, '13323738251' AS contact_phone, '西边' AS area, '石牌坊/红旗区东街市场监管所' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '1590305000' AS phone, '张媛媛' AS contact_name, '1590305000' AS contact_phone, '西边' AS area, '东关大街董欣护肤品/地图搜索大东街社区卫生服务站' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15136760777' AS phone, '李洋1' AS contact_name, '15136760777' AS contact_phone, '西边' AS area, '平原路老四中对面极客通讯' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15136760777B' AS phone, '李洋2' AS contact_name, '15136760777B' AS contact_phone, '西边' AS area, '平原路老四中对面极客通讯' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15137386331' AS phone, '柠檬糖' AS contact_name, '15137386331' AS contact_phone, '西边' AS area, '东大街蚝市自提' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18637308802' AS phone, '张女士' AS contact_name, '18637308802' AS contact_phone, '西边' AS area, '新生巷与西大街美食街交叉口征兵办(胡同最里面)' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15036611288' AS phone, '张萍' AS contact_name, '15036611288' AS contact_phone, '西边' AS area, '恒基时代广场，1号楼1单元1902挂门上就可以了' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '18530710880' AS phone, '珍珠' AS contact_name, '18530710880' AS contact_phone, '西边' AS area, '中心医院门诊大楼3楼A区/周二送-竹馨居2号楼2单元1803，直接挂门把手就行' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '17630171678' AS phone, '弓长' AS contact_name, '17630171678' AS contact_phone, '西边' AS area, '星海假日王府1号楼2单元 403室' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '15736986665' AS phone, '冯苗' AS contact_name, '15736986665' AS contact_phone, '西边' AS area, '派克公馆D座7楼' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '19900010002' AS phone, '世青小学' AS contact_name, '19900010002' AS contact_phone, '西边' AS area, '世青小学/放传达室' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
  UNION ALL
  SELECT '13598660312' AS phone, '静静' AS contact_name, '13598660312' AS contact_phone, '西边' AS area, '宸·瑜伽教练培训学院一楼前台/胖东来德里克斯对' AS detail_address, NULL AS remarks, NULL AS lng, NULL AS lat, 1 AS is_default
) v ON m.`phone` = v.`phone`;
