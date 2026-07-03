-- 087: 報價主檔三表軟刪欄（CR-0110 依 20260702 會議裁決簡化版，冪等）
--
-- 背景：報價主檔 CRUD 原卡在 per-tenant 隔離（CR-0110 §8 九項決策）。20260702
-- 會議拍板「一品牌一 GCP 專案 + 獨立 DB」→ 單品牌 DB 內 code 天然唯一，
-- 不需複合鍵改造/global+override 模型。業主 2026-07-03 裁決殘餘三項：
--   §8-3 三類目一次做；§8-5 軟刪（deleted_at，可復原可稽核）；
--   §8-6 租戶編輯後 is_mock 翻 FALSE + decision_status='已確認'。
-- 本 migration 補三表 deleted_at（軟刪基礎）。

BEGIN;

ALTER TABLE service_catalog  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE material_catalog ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE surcharge_rule   ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

INSERT INTO schema_migrations (version, filename, note)
VALUES ('087', '087-quote-catalog-soft-delete.sql',
        '報價主檔三表加 deleted_at 軟刪欄（CR-0110 CRUD，會議裁決單品牌 DB 簡化版）')
ON CONFLICT (version) DO NOTHING;

COMMIT;
