-- 由 scripts/csv_members_to_sql.py 生成；执行前请确认是否清空 members / member_addresses
SET NAMES utf8mb4;

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17000020001', '慧子', '慧子', '不要敲门，有小宝宝，放门口 | 【导入生成占位手机号】原表电话无效或为空',
  4, 1, 12,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '慧子', '17000020001', NULL, '诚城紫钰北区-52号楼2单元 2202', '不要敲门，有小宝宝，放门口', 113.943552, 35.286371, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13072662392', '方悦', '方悦', '',
  13, 1, 24,
  '月卡', 1, 0, '2026-04-14', 0, 0, '2026-04-14 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '方悦', '13072662392', NULL, '逸品紫晶2号楼3单元703', '', 113.898073, 35.303225, 1, '2026-04-14 00:00:00', '2026-04-14 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13072666882', '李女士', '李女士', '',
  1, 1, 12,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李女士', '13072666882', NULL, '新飞大道与友谊路交叉口-中国平安财产保险股份有限公司', '', 114.663511, 35.206446, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13103737399', '高力', '高力', '小蛋糕',
  11, 1, 24,
  '月卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '高力', '13103737399', NULL, '忆通壹世界从北门进19号楼1单元1502', '小蛋糕', 113.909648, 35.301665, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13126031841', '任', '任', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '任', '13126031841', NULL, '中建海德壹号8—1—2401', '', 113.908732, 35.313637, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13183101221', '聂鑫', '聂鑫', '4月27日开始配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '聂鑫', '13183101221', NULL, '新飞大道和人民路交叉口东南角红旗分局 不要紫甘蓝，打电话，门岗不让房餐', '4月27日开始配送', 113.912088, 35.300142, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13262153309', '黑猫警长 1', '黑猫警长 1', '另行通知 | 【表格别名】黑猫警长 2',
  1, 2, 6,
  '周卡', 0, 0, '2026-04-15', 1, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '黑猫警长 1 | 黑猫警长 2', '13262153309', NULL, '华瑞逸品紫晶8-b 702', '另行通知', 113.936169, 35.306442, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13303733442', '贾瑞', '贾瑞', '放门口，别打电话',
  11, 1, 24,
  '月卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '贾瑞', '13303733442', NULL, '和平路纺织路交叉口隆基新谊城8号楼4单元1501 4月24日休息', '放门口，别打电话', 113.890497, 35.277794, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13323801598', '王辣辣', '王辣辣', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王辣辣', '13323801598', NULL, '藏营大街晨迪托辅，到这里打电话，客户就在店旁边', '', 113.873698, 35.294162, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13333732120', '李飞凡', '李飞凡', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李飞凡', '13333732120', NULL, '溥诚花园一号楼二单元放楼下拍照', '', 113.910871, 35.294726, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13419886000', '毛毛', '毛毛', '送2份后4月23日最后一次 通知冲卡',
  1, 1, 6,
  '月卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '毛毛', '13419886000', NULL, '牧野区兰亭花园4号楼3单元301 放门口', '送2份后4月23日最后一次 通知冲卡', 113.937848, 35.308798, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13462248872', '梁彬', '梁彬', '另行通知',
  24, 1, 24,
  '月卡', 0, 0, '2026-04-22', 1, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '梁彬', '13462248872', NULL, '地税局家属院4号楼一单元1楼西户，', '另行通知', 114.215058, 35.14171, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13462278702', '杨女士', '杨女士', '周六不配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '杨女士', '13462278702', NULL, '互联网大厦一楼到了，跟我电话联系，去取', '周六不配送', 113.929196, 35.296932, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13462279970', '妙甜', '妙甜', '小蛋糕',
  3, 1, 6,
  '月卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '妙甜', '13462279970', NULL, '伟业中央公园25号楼1单元1102', '小蛋糕', 113.929452, 35.309553, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13462363423', '李亚杰', '李亚杰', '另行通知',
  2, 1, 6,
  '周卡', 0, 0, '2026-04-17', 1, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李亚杰', '13462363423', NULL, '互联网大厦2606', '另行通知', 113.929196, 35.296932, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13525000736', '杨颂', '杨颂', '另行通知 | 需要续卡',
  3, 1, 6,
  '周卡', 0, 0, '2026-04-17', 1, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '杨颂', '13525000736', NULL, '豫飞·金色城邦 - 1号楼1单元2503', '另行通知 | 需要续卡', 113.898445, 35.330314, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13569825406', '等待梦的传奇', '等待梦的传奇', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '等待梦的传奇', '13569825406', NULL, '正商金域世家二期7号楼302', '', 113.928686, 35.271387, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13569854800', '王晖', '王晖', '小蛋糕',
  22, 1, 30,
  '月卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王晖', '13569854800', NULL, '中建海德壹号4号楼1101', '小蛋糕', 113.908732, 35.313637, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13598660312', '静静', '静静', '另行通知 | 送小蛋糕',
  5, 1, 6,
  '周卡', 0, 0, '2026-04-13', 1, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '静静', '13598660312', NULL, '宸·瑜伽教练培训学院一楼前台/胖东来德里克斯对', '另行通知 | 送小蛋糕', 113.910704, 35.302676, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13598662337', '丁红丽', '丁红丽', '周四不送餐， 周六不送餐， 周五送餐 4月27日之后正常送餐',
  2, 1, 30,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '丁红丽', '13598662337', NULL, '饮马保利城河南农商银行红旗支行', '周四不送餐， 周六不送餐， 周五送餐 4月27日之后正常送餐', 113.983358, 35.306182, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13598663058', '赵高鹏', '赵高鹏', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '赵高鹏', '13598663058', NULL, '二中市场新飞3号院，4单元4楼。', '', 113.884139, 35.314178, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13623904044', '王海燕', '王海燕', '4月27日',
  6, 1, 6,
  '周卡', 0, 0, '2026-04-16', 1, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王海燕', '13623904044', NULL, '大桥悦时代5号楼1214', '4月27日', 113.901949, 35.285108, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13633737333', '薛源', '薛源', '另行通知',
  6, 1, 6,
  '周卡', 0, 0, '2026-04-19', 1, 0, '2026-04-19 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '薛源', '13633737333', NULL, '牧野区红星发展广场9号楼1901室', '另行通知', 113.908561, 35.315614, 1, '2026-04-19 00:00:00', '2026-04-19 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13673505727', '慧心静语', '慧心静语', '4月25（周六）配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-23', 0, 0, '2026-04-23 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '慧心静语', '13673505727', NULL, '送这里-->松江帕提欧7-2-2001， 打这个电话-->赵丹 18703691218', '4月25（周六）配送', 113.873698, 35.294162, 1, '2026-04-23 00:00:00', '2026-04-23 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13673546284', '职', '职', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '职', '13673546284', NULL, '人民路红房小区2号楼四层西户', '', 113.897822, 35.30317, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13673664084', '李伟', '李伟', '另行通知/找跑腿',
  19, 1, 24,
  '月卡', 0, 0, '2026-04-17', 1, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李伟', '13673664084', NULL, '东大街蚝市自提 / 跑腿送九鼎美庐1号楼二单元903室', '另行通知/找跑腿', 113.865742, 35.320244, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13700736310', '蔷薇儿', '蔷薇儿', '4月27日开始配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '蔷薇儿', '13700736310', NULL, '跨境贸易大厦 19 楼 1911 室', '4月27日开始配送', 113.92679, 35.303589, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13781932085', '婧婧', '婧婧', '另行通知',
  4, 1, 6,
  '周卡', 0, 0, '2026-04-15', 1, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '婧婧', '13781932085', NULL, '宝龙国际社区-8号楼2单元1307', '另行通知', 113.927763, 35.292843, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13781939428', '白玉', '白玉', '',
  12, 1, 24,
  '月卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '白玉', '13781939428', NULL, '牧野区-河师大家属院-20号楼6单元3楼西户', '', 113.90977, 35.323584, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13781991718', '王慧', '王慧', '周五正常配送 周六休息 下周一正常配送',
  2, 1, 30,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王慧', '13781991718', NULL, '红旗区劳动路十中巷芳草苑2号楼1单元1号', '周五正常配送 周六休息 下周一正常配送', 113.897822, 35.30317, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13782557327', '吴戈', '吴戈', '4月27日开始配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '吴戈', '13782557327', NULL, '红旗区振中路与科隆大道交叉口中国工商银行（振中支行）', '4月27日开始配送', 113.894736, 35.274501, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13782570469', '杨女士', '杨女士', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '杨女士', '13782570469', NULL, '华恩城东区10—301', '', 113.955107, 35.306367, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13782739347', '何燕飞', '何燕飞', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '何燕飞', '13782739347', NULL, '建业壹号城邦三期 - 16号楼2单元2703，放在门口', '', 113.916607, 35.28991, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13803735117', '微笑', '微笑', '系统需录入续卡',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-19', 0, 0, '2026-04-19 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '微笑', '13803735117', NULL, '紫锦国际b座写字楼 到了打电话', '系统需录入续卡', 113.889428, 35.26075, 1, '2026-04-19 00:00:00', '2026-04-19 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13837343744', '赵琰', '赵琰', '4月22续卡，一会补充 | 需录入系统',
  7, 1, 12,
  '周卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '赵琰', '13837343744', NULL, '国悦城悦府壹号院4号楼一单元602', '4月22续卡，一会补充 | 需录入系统', 113.903106, 35.289299, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13849362225', '赵女士', '赵女士', '4月24周五配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-23', 0, 0, '2026-04-23 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '赵女士', '13849362225', NULL, '金色奥园小区L2号楼新永基置业前台', '4月24周五配送', 113.914275, 35.282314, 1, '2026-04-23 00:00:00', '2026-04-23 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13849388648', '李文兰', '李文兰', '',
  20, 1, 24,
  '月卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李文兰', '13849388648', NULL, '北干道二建二生活区16号楼6单元1楼东户', '', 113.902049, 35.318095, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13937338601', '岁月静好', '岁月静好', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '岁月静好', '13937338601', NULL, '星海假日王府二期5号楼2单元21楼2103', '', 113.883229, 35.294482, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13937365881', '代女士', '代女士', '4月27日开始配送',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '代女士', '13937365881', NULL, '纺织路祥瑞花园4号楼2单元3楼东户', '4月27日开始配送', 113.898853, 35.278023, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '13938768398', '张娜', '张娜', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张娜', '13938768398', NULL, '1. 段村新村高4号楼6楼西南户/ 周六送这里2. 宝龙世家西门-往北50米中国体育彩票', '', 113.922984, 35.293685, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15003737123', '丁敏', '丁敏', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '丁敏', '15003737123', NULL, '中心医院 5 号楼 2 楼 重症医学科二区', '', 113.866018, 35.296478, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15036624101', '李佳丽', '李佳丽', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李佳丽', '15036624101', NULL, '宝龙葛记红焖 - 放前台', '', 113.92679, 35.303589, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15036630439', '张晓菲', '张晓菲', '另行通知 | 小蛋糕',
  23, 1, 24,
  '月卡', 0, 0, '2026-04-20', 1, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张晓菲', '15036630439', NULL, '大桥悦时代一楼阿迪达斯', '另行通知 | 小蛋糕', 113.901949, 35.285108, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15037311578', '李增艳', '李增艳', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李增艳', '15037311578', NULL, '科隆大道与俊杰路交叉口，俊杰路上富庭酒店前台', '', 113.915988, 35.272854, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15083103158', '洪女士', '洪女士', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '洪女士', '15083103158', NULL, '建业壹号城邦三期 - 23号楼1单元2103', '', 113.916607, 35.28991, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15083130729', '荆琳', '荆琳', '另行通知',
  5, 1, 6,
  '周卡', 0, 0, '2026-04-20', 1, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '荆琳', '15083130729', NULL, '第二人民医院骨科病房楼3楼麻醉科配餐室', '另行通知', 113.878868, 35.315837, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15090322882', '王渤雅', '王渤雅', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王渤雅', '15090322882', NULL, '云信科技园6012', '4月27日开始配送', 113.92679, 35.303589, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15090361727', '一一', '一一', '4月25（周六）配送',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '一一', '15090361727', NULL, '第二人民医院5号楼5楼icu', '4月25（周六）配送', 113.69346, 34.772687, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15090473606', '高子欣', '高子欣', '周五配送，周六休息 | 4月17日续卡',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-19', 0, 0, '2026-04-19 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '高子欣', '15090473606', NULL, '红旗区和平路与向阳路交叉口保险大厦（新乡分公司）门卫处', '周五配送，周六休息 | 4月17日续卡', 113.889167, 35.285474, 1, '2026-04-19 00:00:00', '2026-04-19 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15090498777', '明镜', '明镜', '',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '明镜', '15090498777', NULL, '宝龙国际社区六号楼二单元22楼2208，', '', 113.928677, 35.293446, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15103739799', '郭宁', '郭宁', '另行通知',
  6, 1, 6,
  '周卡', 0, 0, '2026-04-18', 1, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郭宁', '15103739799', NULL, '新乡三胖西侧内部路2栋公寓旁验货办公室', '另行通知', NULL, NULL, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15136726313', '徐', '徐', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-19', 0, 0, '2026-04-19 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '徐', '15136726313', NULL, '四季城萃园2号楼二单元1501', '', 113.898073, 35.303225, 1, '2026-04-19 00:00:00', '2026-04-19 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15136760777', '李洋1', '李洋1', '另行通知 | 【表格别名】李洋2',
  1, 2, 6,
  '周卡', 0, 0, '2026-04-14', 1, 0, '2026-04-14 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李洋1 | 李洋2', '15136760777', NULL, '平原路老四中对面极客通讯', '另行通知', 113.88277, 35.305014, 1, '2026-04-14 00:00:00', '2026-04-14 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15137332596', '常先生', '常先生', '4月27日开始配送',
  7, 1, 12,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '常先生', '15137332596', NULL, '润华翡翠国际3号楼 就一个单元2502', '4月27日开始配送', 113.945085, 35.30664, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15225925871', '李兰', '李兰', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李兰', '15225925871', NULL, '健康路-新世纪花园1号楼4单元4楼北户', '', 113.873585, 35.297966, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15225934857', '张丽', '张丽', '4月27日开始配送',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张丽', '15225934857', NULL, '新乡市人民路社保综合办公楼（公园北门） 一楼保安后面桌子上', '4月27日开始配送', 113.885093, 35.302067, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15225935226', '郝郝', '郝郝', '',
  0, 1, 12,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郝郝', '15225935226', NULL, '枫景上东-6号楼2单元2105', '', 113.92679, 35.303589, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15236640675', '金', '金', '周六休息',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '金', '15236640675', NULL, '人民路新奥燃气公司', '周六休息', 113.908567, 35.390657, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15237302524', '魏', '魏', '',
  5, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '魏', '15237302524', NULL, '新乡市第一人民医院内科楼10楼 呼吸二', '', 113.914557, 35.380624, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15286910838', '张女士', '张女士', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张女士', '15286910838', NULL, '诚诚紫钰北区-58号楼2单元 302', '', NULL, NULL, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15516186586', '张文婷', '张文婷', '',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张文婷', '15516186586', NULL, '卫滨区劳动南街与新原一巷交叉口往西400米五监狱家属院，放门岗', '', 113.883299, 35.266599, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15516623633', '樊洁', '樊洁', '5月6日',
  0, 1, 24,
  '月卡', 0, 0, '2026-05-06', 1, 0, '2026-05-06 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '樊洁', '15516623633', NULL, '健康路29号院五栋3单元一东', '5月6日', 113.868804, 35.299217, 1, '2026-05-06 00:00:00', '2026-05-06 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15517331110', '刘静懿', '刘静懿', '4月27日开始配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '刘静懿', '15517331110', NULL, '周一 - 周五 ： 公安局交警支队 周六：粮食局家属院6号楼三单元三楼左手边 到了打电话下来拿', '4月27日开始配送', NULL, NULL, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15537316006', '王女士', '王女士', '小蛋糕',
  18, 2, 24,
  '月卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王女士', '15537316006', NULL, '伟业中央公园9号楼 - 5单元 - 1001室', '小蛋糕', 113.923141, 35.308421, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王女士', '15537316006', NULL, '国贸大厦A座3楼梵林瑜伽', '小蛋糕', 113.923848, 35.303885, 0, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15537321966', '潘潘', '潘潘', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '潘潘', '15537321966', NULL, '宏力大道东段牧野区人民检察院，门口打电话', '', 113.924426, 35.317971, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15537355888', '陈书文1', '陈书文1', '【表格别名】陈书文2',
  22, 2, 24,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '陈书文1 | 陈书文2', '15537355888', NULL, '在南环，客户每天都说来自提还跑腿配送', '', 113.884133, 35.259411, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15565213209', '宋佳依', '宋佳依', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '宋佳依', '15565213209', NULL, '东升生活城2号楼-4单元-5楼南户 / 从西门进', '', 113.912472, 35.292073, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15565266868', '郭好意', '郭好意', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郭好意', '15565266868', NULL, '互联网大厦一楼到了，跟我电话联系，去取', '', 113.929196, 35.296932, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15565431117', '刘梦', '刘梦', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '刘梦', '15565431117', NULL, '金穗大道西边到头货运场焦作专线，/ 找不到打电话', '', 113.896369, 35.295623, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15565722060', '洋洋', '洋洋', '4月23，24，25配送 | 4月18日续卡',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '洋洋', '15565722060', NULL, '牧野花园西门38-2-1102，送完群里说，给老娘配送的', '4月23，24，25配送 | 4月18日续卡', 113.923237, 35.31572, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15603739778', '路路', '路路', '4月24配送，周六休息',
  11, 1, 24,
  '月卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '路路', '15603739778', NULL, '郊委路-太阳城一期-3号楼201-放家门口/ 4月24正常配送，4月25不送', '4月24配送，周六休息', 113.884704, 35.312646, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15617199993', '丫丫', '丫丫', '小蛋糕',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '丫丫', '15617199993', NULL, '恒基时代广场2号楼2803室/ 2号楼只有一栋楼，目前电梯需要更换，只有一部正常用，学区房人很多，快去了，提前打电话，在楼下等', '小蛋糕', 113.870341, 35.301313, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15637199131', '波波安', '波波安', '4月27日开始配送',
  20, 1, 24,
  '月卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '波波安', '15637199131', NULL, '金谷阳光地带a28号楼1201/从北门进院/挂在门把手上就行', '4月27日开始配送', 113.884045, 35.280928, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15637358860', '郁明1', '郁明1', '【表格别名】郁明2',
  2, 2, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郁明1 | 郁明2', '15637358860', NULL, '送这个-->金宸国际4号楼2单元2楼中户 这里先不送劳动路华悦家园 - 1号楼1单元3楼东', '', 113.884404, 35.278886, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15637359739', '许娜', '许娜', '4月27日开始配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '许娜', '15637359739', NULL, '中心医院 5 号楼 2 楼 重症医学科二区', '4月27日开始配送', 113.866018, 35.296478, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15660557288', '梦琦', '梦琦', '4月27日开始配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '梦琦', '15660557288', NULL, '火电厂家属院9号楼2单元4层东户', '4月27日开始配送', 113.93308, 35.398073, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15670503558', '妍姝', '妍姝', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '妍姝', '15670503558', NULL, '东郡府苑东苑37号楼-东单元三楼西户', '', 113.924576, 35.310662, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15670510280', '菲菲', '菲菲', '不要香菜，不要菠菜 4月22配送',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '菲菲', '15670510280', NULL, '星海假期王府二期1号楼1单元404', '不要香菜，不要菠菜 4月22配送', 113.898104, 35.302982, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15681905560', '几', '几', '',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '几', '15681905560', NULL, '宝龙环湖珑寓3号楼802（从消防电梯上）', '', 113.928102, 35.294161, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15690794444', '毛艳飞', '毛艳飞', '4月23日续卡',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '毛艳飞', '15690794444', NULL, '紫郡18号楼二单元 1603室', '4月23日续卡', 113.938082, 35.298697, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15716680808', '郭艳', '郭艳', '',
  20, 1, 24,
  '月卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郭艳', '15716680808', NULL, '星海假日王府二期1号楼3单元304', '', 113.897822, 35.303003, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15727396999', '珠珠1', '珠珠1', '另行通知 | 【表格别名】珠珠2',
  6, 2, 6,
  '周卡', 0, 0, '2026-04-15', 1, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '珠珠1 | 珠珠2', '15727396999', NULL, '丰华街建业森林半岛三号楼17楼东户', '另行通知', 113.904595, 35.259904, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15737308925', '小珊', '小珊', '4月27日开始配送',
  6, 1, 6,
  '次卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '小珊', '15737308925', NULL, '振中街三十二中对面姜力头道(振中街店)', '4月27日开始配送', 113.894931, 35.276037, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15836018866', '毛琳', '毛琳', '4月27日开始配送 | 小蛋糕',
  24, 1, 24,
  '月卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '毛琳', '15836018866', NULL, '新飞大道高远路新乡市人民检察院', '4月27日开始配送 | 小蛋糕', 113.901649, 35.277033, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15836072090', '栗郭佳1', '栗郭佳1', '4月25（周六）配送 | 【表格别名】栗郭佳2',
  5, 4, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '栗郭佳1 | 栗郭佳2', '15836072090', NULL, '周一 - 周五 和平路小学门岗 周六 上海城小区东区C10号楼一单元1301室', '4月25（周六）配送', NULL, NULL, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15836176491', '泡泡', '泡泡', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '泡泡', '15836176491', NULL, '富春园B区5号楼3单元5楼西户', '4月27日开始配送', NULL, NULL, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15837300112', '莹莹', '莹莹', '4月27日开始配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '莹莹', '15837300112', NULL, '东如意大厦旁边的新中大道邮政银行 （邮政消费金融中心）', '4月27日开始配送', 113.931115, 35.366715, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15837301078', '张', '张', '4月27日开始配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张', '15837301078', NULL, '新乡市外国语小学', '4月27日开始配送', 113.874673, 35.294482, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15893808153', '王', '王', '另行通知',
  4, 1, 6,
  '周卡', 0, 0, '2026-04-15', 1, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王', '15893808153', NULL, '河南省精神病卫生中心-综合病房楼9楼 心身医学一科医生办公室', '另行通知', NULL, NULL, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15893822338', '郑喆', '郑喆', '明天一直到 29 日都不用送餐，因为出差了不在新乡。',
  20, 1, 24,
  '月卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郑喆', '15893822338', NULL, '国贸大厦c座8楼河南师大方正律师事务所', '明天一直到 29 日都不用送餐，因为出差了不在新乡。', 113.923086, 35.304677, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15893870386', '路仙', '路仙', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '路仙', '15893870386', NULL, '西大街花啡花在往西 米组', '', 113.875357, 35.302213, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15903018794', '朱女士', '朱女士', '未录入系统',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-22', 0, 0, '2026-04-22 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '朱女士', '15903018794', NULL, '新盾嘉苑28号楼6单元4楼401', '未录入系统', 113.872459, 35.26329, 1, '2026-04-22 00:00:00', '2026-04-22 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '1590305000', '张媛媛', '张媛媛', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张媛媛', '1590305000', NULL, '东关大街董欣护肤品/地图搜索大东街社区卫生服务站', '', 113.931668, 35.036149, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15903096086', '小馨', '小馨', '4月25（周六）配送',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '小馨', '15903096086', NULL, '恒生世家B座808', '4月25（周六）配送', 113.92679, 35.303589, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15903875314', '羊', '羊', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '羊', '15903875314', NULL, '康桥美庭-4号楼二单元二楼东', '', 113.940459, 35.309886, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15903889925', '宁宁', '宁宁', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '宁宁', '15903889925', NULL, '互联网大厦2606', '', 113.929196, 35.296932, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15903899656', '林辉', '林辉', '小蛋糕',
  16, 1, 24,
  '月卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '林辉', '15903899656', NULL, '伟业中央公园16号楼 - 1单元 - 1502室 / 用里面的电梯，不刷卡', '小蛋糕', 113.926428, 35.308124, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15936550650', '段女士', '段女士', '另行通知',
  4, 1, 6,
  '周卡', 0, 0, '2026-04-18', 1, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '段女士', '15936550650', NULL, '人民路辉龙花园F座6楼西户', '另行通知', 113.874755, 35.301654, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15937319177', '菲', '菲', '4月27日开始配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '菲', '15937319177', NULL, '建业壹号城邦三期 - 19号楼10楼中户，放门口就行', '4月27日开始配送', 113.916607, 35.28991, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15937321666', '左磊', '左磊', '另行通知',
  5, 1, 6,
  '周卡', 0, 0, '2026-04-20', 1, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '左磊', '15937321666', NULL, '周二配送这个地址1. 东站春天里广场南门茅台酱香店 2. 理想城16号楼二单元6楼东', '另行通知', 113.902527, 35.296399, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '15993059291', '任志培', '任志培', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '任志培', '15993059291', NULL, '金穗大道五星座C座1201室', '4月27日开始配送', 113.891516, 35.295352, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '16627755424', '泡泡', '泡泡', '小蛋糕',
  12, 1, 24,
  '月卡', 1, 0, '2026-04-14', 0, 0, '2026-04-14 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '泡泡', '16627755424', NULL, '都市名城1号楼1单元11楼1106/别打电话', '小蛋糕', 113.879122, 35.312767, 1, '2026-04-14 00:00:00', '2026-04-14 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '16637365665', '云上', '云上', '',
  3, 1, 7,
  '周卡', 1, 0, '2026-04-14', 0, 0, '2026-04-14 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '云上', '16637365665', NULL, '中建海德壹号9号楼1单元809', '', 113.908732, 35.313637, 1, '2026-04-14 00:00:00', '2026-04-14 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '16638392000', '王丽娜', '王丽娜', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王丽娜', '16638392000', NULL, '葛记烩面(劳动桥店)', '', 113.879609, 35.307468, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '16691810509', '刘璟辰', '刘璟辰', '4月27日开始配送',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '刘璟辰', '16691810509', NULL, '竹馨居-13号楼1403/早一点送', '4月27日开始配送', 113.93149, 35.308815, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17337337775', '焦点', '焦点', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '焦点', '17337337775', NULL, '派克公馆D座2111', '', 113.899971, 35.29638, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17337399477', '边边', '边边', '',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-23', 0, 0, '2026-04-23 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '边边', '17337399477', NULL, '互联网大厦3808', '', 113.929196, 35.296932, 1, '2026-04-23 00:00:00', '2026-04-23 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17371250315', '一只三文鱼', '一只三文鱼', '不要洋葱葱姜蒜',
  1, 1, 12,
  '周卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '一只三文鱼', '17371250315', NULL, '牧野区-二十二所第一生活区-2号楼1单元3楼西', '不要洋葱葱姜蒜', 113.902982, 35.310378, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17516019965', '叶子萌', '叶子萌', '',
  0, 1, 1,
  '次卡', 1, 0, '2026-04-19', 0, 1, '2026-04-19 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '叶子萌', '17516019965', NULL, '店内自取', '', NULL, NULL, 1, '2026-04-19 00:00:00', '2026-04-19 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17603731607', '李雷', '李雷', '4月25（周六）配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李雷', '17603731607', NULL, '鲲鹏昌建云溪湾2号楼1单元2302', '4月25（周六）配送', 113.945569, 35.303613, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17630170801', '小宁', '小宁', '另行通知',
  6, 1, 6,
  '周卡', 0, 0, '2026-04-17', 1, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '小宁', '17630170801', NULL, '发现生活咖啡馆（文化街店）放前台即可', '另行通知', 113.87421, 35.284899, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17630212580', '朱', '朱', '4月27日配送 或者51节后配送 | 需要续卡 | 请假一天',
  6, 1, 6,
  '周卡', 0, 0, '2026-04-20', 1, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '朱', '17630212580', NULL, '紫锦国际b座写字楼 到了打电话', '4月27日配送 或者51节后配送 | 需要续卡 | 请假一天', 113.889428, 35.26075, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17637319626', '郭优优', '郭优优', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郭优优', '17637319626', NULL, '豫程小区八号院一单元 8楼西南户 （地下停车场上面临街白楼）', '', 113.888119, 35.303257, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17637325330', '郝丽丽', '郝丽丽', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郝丽丽', '17637325330', NULL, '松江帕提欧 2-2-1203', '4月27日开始配送', 113.92679, 35.303589, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17637354933', '赵鑫', '赵鑫', '4月27日开始配送',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '赵鑫', '17637354933', NULL, '紫锦国际b座写字楼 到了打电话', '4月27日开始配送', 113.889428, 35.26075, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17651958426', '潘豆儿', '潘豆儿', '4月27日开始配送',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '潘豆儿', '17651958426', NULL, '河南医药大学第三附属医院-党校对面，打电话', '4月27日开始配送', 115.674049, 34.395047, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17656176273', '张晨晗', '张晨晗', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张晨晗', '17656176273', NULL, '河南师范大学附属中学收发室/说给学生送饭', '', 113.912868, 35.322603, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17737279302', '郭潇', '郭潇', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郭潇', '17737279302', NULL, '松江帕提欧小区8号楼1单元1201', '4月27日开始配送', 113.92882, 35.288353, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17739191399', '丰萍', '丰萍', '4月27日开始配送 | 小蛋糕',
  15, 1, 24,
  '月卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '丰萍', '17739191399', NULL, '送这个-->体育中心北区102号 DJI大疆吧 这个不送：泰安路新二街交叉口南 30米，DJI倚天摄影器材', '4月27日开始配送 | 小蛋糕', 113.928077, 35.296992, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17772874331', '陈红燕', '陈红燕', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '陈红燕', '17772874331', NULL, '新乡市华兰大道339号新电花园，7号楼10楼1003。', '', 113.890708, 35.280767, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17839858350', '柳', '柳', '4月27日开始配送',
  6, 1, 6,
  '次卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '柳', '17839858350', NULL, '国际大厦东侧/红旗渠司法局渠东司法所', '4月27日开始配送', 113.89399, 35.298556, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '17839889133', '王攀', '王攀', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王攀', '17839889133', NULL, '周12456送这里1:四季城萃园8号楼2单元903，放门口就行 周三送这里:红旗区人民路与新五街交叉口，教育局', '', 113.90825, 35.291381, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18003736700', '张倩', '张倩', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张倩', '18003736700', NULL, '东如意大厦423', '', 114.001522, 35.297799, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18039633337', '吴娜伊', '吴娜伊', '4月27日开始配送，周六日不配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '吴娜伊', '18039633337', NULL, '绿科共创中心大厦一层商铺 星光传媒前台', '4月27日开始配送，周六日不配送', NULL, NULL, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18236154492', '王女士', '王女士', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王女士', '18236154492', NULL, '周六建业壹号城邦三期-30号楼1楼 周三配送到这里-伟业双子塔南塔放601门口铁皮柜上', '', 113.929727, 35.306622, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18237312999', '刘', '刘', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '刘', '18237312999', NULL, '学院路牧北小区（传仁堂大药房后面小高层）9层西南户', '4月27日开始配送', 113.907246, 35.318071, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18237366612', '王雯雯', '王雯雯', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王雯雯', '18237366612', NULL, '建业世和府 2-1-902', '', 113.951312, 35.289979, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18238659505', '郭', '郭', '另行通知',
  6, 1, 6,
  '周卡', 0, 0, '2026-04-16', 1, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郭', '18238659505', NULL, '卫滨区解放大道紫台一品一期八号楼10楼A', '另行通知', 113.864416, 35.291684, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18238778808', '梅子', '梅子', '另行通知',
  2, 1, 6,
  '周卡', 0, 0, '2026-04-15', 1, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '梅子', '18238778808', NULL, '大桥云锦府3 号楼2单元902', '另行通知', 113.933099, 35.31606, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18303612777', '王纯', '王纯', '4月25送2份',
  1, 2, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王纯', '18303612777', NULL, '大桥云锦府7号楼2单元601', '4月25送2份', 113.933632, 35.315195, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18317576999', '李琳', '李琳', '4月27日开始配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李琳', '18317576999', NULL, '世纪村8号楼2单元 603 / 楼下门禁 #1235#', '4月27日开始配送', 113.933063, 35.302791, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18337315986', '周先生', '周先生', '',
  22, 1, 24,
  '月卡', 1, 0, '2026-04-23', 0, 0, '2026-04-23 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '周先生', '18337315986', NULL, '正商城二期（祥园）17号楼一单元2802室 电话如果打不通，放门口即可', '', NULL, NULL, 1, '2026-04-23 00:00:00', '2026-04-23 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18337325613', '李瑞', '李瑞', '4月27日开始配送',
  4, 1, 12,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李瑞', '18337325613', NULL, '道清路-青青家园-7号楼-西单元-4楼西户', '4月27日开始配送', 113.909381, 35.267725, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18437381760', '郭明月', '郭明月', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郭明月', '18437381760', NULL, '裕康家园2号楼一单元5楼505', '', 113.874327, 35.299905, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18437919028', '周末', '周末', '4月24周五配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '周末', '18437919028', NULL, '华兰大道牧野大道交叉口五号食堂4楼外卖架', '4月24周五配送', 113.911332, 35.280584, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18439082533', '靳豆豆', '靳豆豆', '另行通知 | 小蛋糕',
  2, 1, 6,
  '周卡', 0, 0, '2026-04-15', 1, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '靳豆豆', '18439082533', NULL, '盛大凯旋城西门13号楼1205', '另行通知 | 小蛋糕', 113.94898, 35.308821, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18530206408', '木村', '木村', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '木村', '18530206408', NULL, '宝龙澳门街4号门-one-11美发店', '', 113.92679, 35.303589, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18532297750', '李嘉伟', '李嘉伟', '不要芝麻 | 小蛋糕',
  12, 1, 24,
  '月卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李嘉伟', '18532297750', NULL, '牧野区荣校路-龙湖景庭-2号楼1单元605放到门口水桶上', '不要芝麻 | 小蛋糕', 113.909996, 35.311376, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18537301666', '崔崔', '崔崔', '另行通知',
  1, 1, 24,
  '月卡', 0, 0, '2026-04-16', 1, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '崔崔', '18537301666', NULL, '宝龙世家4号楼二单元 3202', '另行通知', 113.923696, 35.294083, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18537306792', '刘悟饭', '刘悟饭', '',
  18, 1, 24,
  '月卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '刘悟饭', '18537306792', NULL, '商会大厦B座8楼电梯门口外卖桌', '', 113.931846, 35.296945, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18568256780', '张敬雪', '张敬雪', '另行通知',
  4, 1, 6,
  '周卡', 0, 0, '2026-04-18', 1, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张敬雪', '18568256780', NULL, '和平大道安乐巷新乡县委家属院4号楼2单月2楼东', '另行通知', 112.087339, 34.126302, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18603733011', '邹志毅', '邹志毅', '另行通知',
  2, 2, 6,
  '周卡', 0, 0, '2026-04-17', 1, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '邹志毅', '18603733011', NULL, '东如意大厦 404 室', '', 114.001522, 35.297799, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '邹志毅', '18603733011', NULL, '人民路新中大道交叉口星海如意大厦 404 室', '另行通知', 114.200841, 35.157749, 0, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18613730000', '苑', '苑', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '苑', '18613730000', NULL, '竹馨居-11号楼一单元401', '', 113.933792, 35.308823, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18623737961', '王大喜', '王大喜', '需要续卡',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王大喜', '18623737961', NULL, '新五街东方家园2号楼2单元7楼东', '需要续卡', 113.939756, 35.306781, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18637308802', '张女士', '张女士', '',
  16, 1, 24,
  '月卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张女士', '18637308802', NULL, '新生巷与西大街美食街交叉口征兵办(胡同最里面)', '', 114.200841, 35.157749, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18637315781', '贾女士', '贾女士', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-18', 0, 0, '2026-04-18 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '贾女士', '18637315781', NULL, '卫滨区南桥街道新运二三号院5号楼三单元2楼东户', '', 113.865377, 35.293795, 1, '2026-04-18 00:00:00', '2026-04-18 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18637315978', '井晶', '井晶', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 1, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '井晶', '18637315978', NULL, '自提', '4月27日开始配送', NULL, NULL, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18637361993', '郑雪雅', '郑雪雅', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '郑雪雅', '18637361993', NULL, '健民二巷 - 东方国际小区- 3号楼603', '', 113.867134, 35.301529, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18637368608', 'TPQ', 'TPQ', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-19', 0, 0, '2026-04-19 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, 'TPQ', '18637368608', NULL, '周六配送到LINLEE林里大桥悦时代店 竹馨居9号楼2单元25楼2501 LINLEE林里大胖店 LINLEE林里宝龙店', '', 113.935566, 35.309329, 1, '2026-04-19 00:00:00', '2026-04-19 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18637369543', '气球1', '气球1', '需要续卡 | 【表格别名】气球2',
  0, 2, 6,
  '周卡', 1, 0, '2026-04-19', 0, 0, '2026-04-19 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '气球1 | 气球2', '18637369543', NULL, '互联网大厦517', '需要续卡', 113.929196, 35.296932, 1, '2026-04-19 00:00:00', '2026-04-19 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18637370413', '蒋珊', '蒋珊', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '蒋珊', '18637370413', NULL, '进达花园-斐然婚纱前台', '', 113.934995, 35.298212, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18638315659', '张云', '张云', '另行通知',
  24, 1, 24,
  '月卡', 0, 0, '2026-04-15', 1, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张云', '18638315659', NULL, '新飞大道道-清路新乡融诚信息咨询中心前台', '另行通知', 113.909756, 35.268329, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18695922228', '33', '33', '',
  12, 1, 24,
  '月卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '33', '18695922228', NULL, '火电厂家属院9号楼2单元4楼东户', '', 113.93308, 35.398073, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18695939222', '牛臻', '牛臻', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-15', 0, 1, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '牛臻', '18695939222', NULL, '店内自取', '', NULL, NULL, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18703691218', '赵丹', '赵丹', '4月27日开始配送',
  6, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '赵丹', '18703691218', NULL, '松江帕提欧7-2-2001', '4月27日开始配送', 113.92679, 35.303589, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18737306642', '文女士', '文女士', '另行通知',
  17, 1, 24,
  '月卡', 0, 0, '2026-04-13', 1, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '文女士', '18737306642', NULL, '火电厂家属院3号楼2单元1楼东户', '另行通知', 113.93308, 35.398073, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18737356232', '雪雪 1', '雪雪 1', '4月18日续周卡 | 小蛋糕 | 【表格别名】雪雪 2',
  26, 2, 30,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '雪雪 1 | 雪雪 2', '18737356232', NULL, '东振路和新一街交叉口-新时代大厦放3A进门处', '4月18日续周卡 | 小蛋糕', 113.918341, 35.271614, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18738372222', '周周', '周周', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-14', 0, 0, '2026-04-14 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '周周', '18738372222', NULL, '世纪村15号楼2单元3楼东户', '', 113.931817, 35.305639, 1, '2026-04-14 00:00:00', '2026-04-14 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18790525999', '刘', '刘', '',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-20', 0, 0, '2026-04-20 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '刘', '18790525999', NULL, '国悦城1期4号楼1单元802', '', 113.903106, 35.289299, 1, '2026-04-20 00:00:00', '2026-04-20 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18790545856', '李亚', '李亚', '',
  23, 1, 30,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '李亚', '18790545856', NULL, '东大街蚝市自提', '', 113.886554, 35.303271, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18810891478', '黄芒果', '黄芒果', '4月25日送2份，然后结束',
  2, 2, 6,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '黄芒果', '18810891478', NULL, '牧野花园 28号楼2单元1202', '4月25日送2份，然后结束', 113.925786, 35.316116, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18837301139', '付洁', '付洁', '另行通知',
  6, 1, 6,
  '周卡', 0, 0, '2026-04-21', 1, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '付洁', '18837301139', NULL, '新中大道星海中心666号移动公司', '另行通知', 113.931909, 35.299702, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18837311116', '张1', '张1', '【表格别名】张2',
  2, 2, 6,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张1 | 张2', '18837311116', NULL, '星海假日王府一期3号楼2203', '', 113.883229, 35.294482, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18837339333', '张', '张', '4月27日开始配送',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '张', '18837339333', NULL, '裕康家园4号楼1004', '4月27日开始配送', 113.874576, 35.299949, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18838706190', '石炎', '石炎', '4月25（周六）配送',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '石炎', '18838706190', NULL, '健康路与劳动路交叉口西北角-三石町寿司', '4月25（周六）配送', 113.936786, 35.308951, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18838753293', '王璐', '王璐', '',
  0, 1, 6,
  '周卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '王璐', '18838753293', NULL, '阳光体育(剑桥城店) 旁边的小门上2楼/找不到打电话', '', 113.907857, 35.320074, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18838766185', '大橘子', '大橘子', '周五配送',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '大橘子', '18838766185', NULL, '中国建设银行(新乡市区支行)4楼，从楼后面进，上电梯 保安要是拦，你给小姐姐打电话', '周五配送', 113.872383, 35.301729, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18838769517', '任如意', '任如意', '不吃葱 不吃香菜 不吃蒜。 暂时不送转了2月钱',
  21, 1, 48,
  '月卡', 1, 0, '2026-04-14', 0, 0, '2026-04-14 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '任如意', '18838769517', NULL, '河南省新乡市红旗区新飞建业府6号楼1单元301/ 单元门密码8888 放家门口就行', '不吃葱 不吃香菜 不吃蒜。 暂时不送转了2月钱', 113.904683, 35.275613, 1, '2026-04-14 00:00:00', '2026-04-14 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18839267876', '孙', '孙', '4月25（周六）配送',
  0, 1, 1,
  '次卡', 1, 0, '2026-04-13', 0, 0, '2026-04-13 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '孙', '18839267876', NULL, '金穗大道福兴国际小区四号搂23楼2303', '4月25（周六）配送', 113.902907, 35.297797, 1, '2026-04-13 00:00:00', '2026-04-13 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18903806687', '葛莹', '葛莹', '另行通知',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-21', 0, 0, '2026-04-21 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '葛莹', '18903806687', NULL, '星海假日王府二期七号楼一单元2102', '另行通知', 113.883229, 35.294482, 1, '2026-04-21 00:00:00', '2026-04-21 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18937355055', '荆京', '荆京', '周六休息',
  1, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '荆京', '18937355055', NULL, '中心医院门诊楼跟内科楼拐角那的咖啡厅打电话来拿', '周六休息', 113.865604, 35.29714, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18937367910', '周小鱼', '周小鱼', '',
  4, 1, 6,
  '周卡', 1, 0, '2026-04-23', 0, 0, '2026-04-23 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '周小鱼', '18937367910', NULL, '跨境贸易大厦 19 楼 1911 室', '', 113.92679, 35.303589, 1, '2026-04-23 00:00:00', '2026-04-23 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '18937390321', '朱紫豪', '朱紫豪', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-17', 0, 0, '2026-04-17 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '朱紫豪', '18937390321', NULL, '人民东路87号院西单元三楼', '', 113.897205, 35.299685, 1, '2026-04-17 00:00:00', '2026-04-17 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '19273733751', '师女士', '师女士', '4月27日开始配送 | 小蛋糕',
  19, 1, 24,
  '月卡', 1, 0, '2026-04-27', 0, 0, '2026-04-27 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '师女士', '19273733751', NULL, '国贸大厦A座606', '4月27日开始配送 | 小蛋糕', 113.923848, 35.303885, 1, '2026-04-27 00:00:00', '2026-04-27 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '19337380888', '周周', '周周', '',
  13, 1, 24,
  '月卡', 1, 0, '2026-04-14', 0, 0, '2026-04-14 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '周周', '19337380888', NULL, '正商城二期 19号楼2302', '', 113.92679, 35.303589, 1, '2026-04-14 00:00:00', '2026-04-14 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '19561960029', '方', '方', '',
  2, 1, 6,
  '周卡', 1, 0, '2026-04-16', 0, 0, '2026-04-16 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '方', '19561960029', NULL, '第二人民医院南侧外贸家属院北楼三单元三楼东', '', 113.879618, 35.314212, 1, '2026-04-16 00:00:00', '2026-04-16 00:00:00'
);

INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  '19837371077', '夏天', '夏天', '',
  3, 1, 6,
  '周卡', 1, 0, '2026-04-15', 0, 0, '2026-04-15 00:00:00'
);
SET @__member_id = LAST_INSERT_ID();

INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, '夏天', '19837371077', NULL, '辉龙阳光城怡苑21号楼四单元六楼东户412室', '', 113.91589, 35.300133, 1, '2026-04-15 00:00:00', '2026-04-15 00:00:00'
);

