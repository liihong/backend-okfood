-- 会员主键由 phone 改为自增 id；子表外键改为引用 members.id
-- 执行前请备份数据库。MySQL 8.0+ InnoDB。

SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;

ALTER TABLE member_addresses DROP FOREIGN KEY fk_member_addresses_member;
ALTER TABLE delivery_logs DROP FOREIGN KEY fk_delivery_user;
ALTER TABLE balance_logs DROP FOREIGN KEY fk_balance_user;
ALTER TABLE member_card_orders DROP FOREIGN KEY fk_member_card_orders_member;

SET FOREIGN_KEY_CHECKS = 1;

-- members：id 为主键，phone 唯一
ALTER TABLE members
  DROP PRIMARY KEY,
  ADD COLUMN id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST,
  ADD UNIQUE KEY uk_members_phone (phone);

-- member_addresses：member_id替代 member_phone
ALTER TABLE member_addresses
  ADD COLUMN member_id BIGINT UNSIGNED NULL AFTER id;

UPDATE member_addresses ma  INNER JOIN members m ON ma.member_phone = m.phone
  SET ma.member_id = m.id;

ALTER TABLE member_addresses
  DROP INDEX idx_member_addresses_member,
  DROP INDEX idx_member_addresses_member_default,
  DROP COLUMN member_phone;

ALTER TABLE member_addresses
  MODIFY member_id BIGINT UNSIGNED NOT NULL,
  ADD KEY idx_member_addresses_member (member_id),
  ADD KEY idx_member_addresses_member_default (member_id, is_default),
  ADD CONSTRAINT fk_member_addresses_member FOREIGN KEY (member_id) REFERENCES members (id)
    ON DELETE CASCADE ON UPDATE CASCADE;

-- delivery_logs：member_id 替代 user_id(phone)
ALTER TABLE delivery_logs
  ADD COLUMN member_id BIGINT UNSIGNED NULL AFTER id;

UPDATE delivery_logs d
  INNER JOIN members m ON d.user_id = m.phone
  SET d.member_id = m.id;

ALTER TABLE delivery_logs
  DROP INDEX uk_delivery_user_date;

ALTER TABLE delivery_logs
  DROP COLUMN user_id;

ALTER TABLE delivery_logs
  MODIFY member_id BIGINT UNSIGNED NOT NULL,
  ADD UNIQUE KEY uk_delivery_member_date (member_id, delivery_date),
  ADD CONSTRAINT fk_delivery_member FOREIGN KEY (member_id) REFERENCES members (id)
    ON DELETE RESTRICT ON UPDATE CASCADE;

-- balance_logs
ALTER TABLE balance_logs
  ADD COLUMN member_id BIGINT UNSIGNED NULL AFTER id;

UPDATE balance_logs b
  INNER JOIN members m ON b.user_id = m.phone
  SET b.member_id = m.id;

ALTER TABLE balance_logs
  DROP INDEX idx_balance_user_created;

ALTER TABLE balance_logs
  DROP COLUMN user_id;

ALTER TABLE balance_logs
  MODIFY member_id BIGINT UNSIGNED NOT NULL,
  ADD KEY idx_balance_member_created (member_id, created_at),
  ADD CONSTRAINT fk_balance_member FOREIGN KEY (member_id) REFERENCES members (id)
    ON DELETE RESTRICT ON UPDATE CASCADE;

-- member_card_orders
ALTER TABLE member_card_orders
  ADD COLUMN member_id BIGINT UNSIGNED NULL AFTER id;

UPDATE member_card_orders o
  INNER JOIN members m ON o.member_phone = m.phone
  SET o.member_id = m.id;

ALTER TABLE member_card_orders
  DROP INDEX idx_member_card_orders_phone;

ALTER TABLE member_card_orders
  DROP COLUMN member_phone;

ALTER TABLE member_card_orders
  MODIFY member_id BIGINT UNSIGNED NOT NULL,
  ADD KEY idx_member_card_orders_member (member_id),
  ADD CONSTRAINT fk_member_card_orders_member FOREIGN KEY (member_id) REFERENCES members (id)
    ON DELETE CASCADE ON UPDATE CASCADE;
