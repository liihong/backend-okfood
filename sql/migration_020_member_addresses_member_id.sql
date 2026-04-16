-- 补齐 member_addresses.member_id（与 app.models.member_address / schema.sql 一致）
--
-- 背景：若库曾跳过 migration_019 中 member_addresses 段，或表被误建为无关联列，
-- 会出现 Unknown column 'member_addresses.member_id'。
--
-- 若仍存在 member_phone：请先执行 migration_019_members_surrogate_id.sql 全文；
-- 本脚本仅处理「无 member_phone、无 member_id」的残缺表（常见为空表）。
--
-- MySQL 8.0+ InnoDB

SET NAMES utf8mb4;

ALTER TABLE member_addresses
  ADD COLUMN member_id BIGINT UNSIGNED NOT NULL COMMENT 'members.id' AFTER id,
  ADD KEY idx_member_addresses_member (member_id),
  ADD KEY idx_member_addresses_member_default (member_id, is_default),
  ADD CONSTRAINT fk_member_addresses_member FOREIGN KEY (member_id) REFERENCES members (id)
    ON DELETE CASCADE ON UPDATE CASCADE;
