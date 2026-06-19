-- 045-technician-payout-rule.sql
--
-- WHY（CR-0037 / 業主「一起做」）：
--   esales PhaseII FinanceSettlement sheet 21「Technician Payout Rule」有 69 筆師傅拆帳草稿
--   （23 服務 × A/B/C 級別 + 夜間/急件加成率），但 code 目前拆帳硬編 80%（ADR-0041），與
--   服務/等級無關。依決議 5 把 sheet 21 值當 mock 灌為主檔（仿 CR-0034 catalog）。
--
-- WHAT：
--   technician_payout_rule 主檔表 + 69 筆 mock seed（人工轉寫自 sheet 21，is_mock=TRUE，
--   decision_status：A/B=draft、C=draft_review 特定服務需覆核）。base_payout=基礎拆帳，
--   night/urgent_surcharge_pct=夜間/急件加成率（全 0.2/0.15）。
--
-- 性質：DB schema + mock seed（仿 CR-0034），idempotent（ON CONFLICT(rule_id) DO NOTHING）。
--   mock-first：值為 esales sheet 21 草稿（python 抽出後人工核對轉寫，非自動 import 不可信來源），
--     全 is_mock=TRUE（DEFAULT），正式值待業主 Q-09 師傅分潤確認。
--   tenant_id：seed 全 NULL = 全域共享主檔（單租戶 Chairlock；仿 CR-0034「tenant_id IS NULL OR
--     = 該租戶」查詢隔離）；未來租戶自訂規則時插 tenant_id 非 NULL。
--   NOT wired：reconciliation 拆帳重算（× 0.8 → 查表）待 Phase II（需 work_orders 夜間/急件旗標）。

CREATE TABLE IF NOT EXISTS technician_payout_rule (
    rule_id              VARCHAR(60) PRIMARY KEY,
    service_code         VARCHAR(40) NOT NULL,
    service_name         VARCHAR(120),
    level_id             VARCHAR(10) NOT NULL,        -- LV-A / LV-B / LV-C
    base_payout          NUMERIC(12,2) NOT NULL,      -- 基礎拆帳（內部，RBAC 遮蔽）
    night_surcharge_pct  NUMERIC(5,4) NOT NULL DEFAULT 0,
    urgent_surcharge_pct NUMERIC(5,4) NOT NULL DEFAULT 0,
    currency             VARCHAR(8) NOT NULL DEFAULT 'TWD',
    effective_date       DATE,
    expiry_date          DATE,
    decision_status      VARCHAR(30) NOT NULL DEFAULT 'draft',
    is_mock              BOOLEAN NOT NULL DEFAULT TRUE,
    tenant_id            UUID,
    created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_payout_rule_service ON technician_payout_rule(service_code, level_id);

COMMENT ON TABLE technician_payout_rule IS 'CR-0037 師傅拆帳規則主檔（esales sheet21 mock）；base_payout 為內部敏感（RBAC 遮蔽）；正式值待 Q-09 師傅分潤';
COMMENT ON COLUMN technician_payout_rule.base_payout IS '基礎拆帳（內部成本，僅後台 admin/ops 可見）；mock 待 esales Q-09';

INSERT INTO technician_payout_rule
  (rule_id, service_code, service_name, level_id, base_payout, night_surcharge_pct,
   urgent_surcharge_pct, currency, effective_date, expiry_date, decision_status)
VALUES
  ('PAY-SVC-RES-001-A','SVC-RES-001','到府檢測','LV-A',150,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-001-B','SVC-RES-001','到府檢測','LV-B',100,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-001-C','SVC-RES-001','到府檢測','LV-C',100,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-RES-002-A','SVC-RES-002','住宅開鎖一般鎖','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-002-B','SVC-RES-002','住宅開鎖一般鎖','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-002-C','SVC-RES-002','住宅開鎖一般鎖','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-RES-003-A','SVC-RES-003','住宅開鎖多段鎖','LV-A',650,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-003-B','SVC-RES-003','住宅開鎖多段鎖','LV-B',500,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-003-C','SVC-RES-003','住宅開鎖多段鎖','LV-C',450,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-RES-004-A','SVC-RES-004','商業空間開鎖','LV-A',650,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-004-B','SVC-RES-004','商業空間開鎖','LV-B',500,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-004-C','SVC-RES-004','商業空間開鎖','LV-C',450,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-RES-005-A','SVC-RES-005','機械鎖更換','LV-A',650,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-005-B','SVC-RES-005','機械鎖更換','LV-B',500,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-005-C','SVC-RES-005','機械鎖更換','LV-C',450,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-RES-006-A','SVC-RES-006','加裝副鎖','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-006-B','SVC-RES-006','加裝副鎖','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-RES-006-C','SVC-RES-006','加裝副鎖','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-001-A','SVC-ELK-001','電子鎖安裝（本店購買）','LV-A',650,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-001-B','SVC-ELK-001','電子鎖安裝（本店購買）','LV-B',500,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-001-C','SVC-ELK-001','電子鎖安裝（本店購買）','LV-C',450,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-002-A','SVC-ELK-002','電子鎖代工安裝（客戶自備鎖）','LV-A',650,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-002-B','SVC-ELK-002','電子鎖代工安裝（客戶自備鎖）','LV-B',500,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-002-C','SVC-ELK-002','電子鎖代工安裝（客戶自備鎖）','LV-C',450,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-003-A','SVC-ELK-003','電子鎖故障檢測','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-003-B','SVC-ELK-003','電子鎖故障檢測','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-003-C','SVC-ELK-003','電子鎖故障檢測','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-004-A','SVC-ELK-004','電子鎖維修工資','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-004-B','SVC-ELK-004','電子鎖維修工資','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-004-C','SVC-ELK-004','電子鎖維修工資','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-005-A','SVC-ELK-005','面板/觸控無反應檢測','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-005-B','SVC-ELK-005','面板/觸控無反應檢測','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-005-C','SVC-ELK-005','面板/觸控無反應檢測','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-006-A','SVC-ELK-006','異常耗電檢測','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-006-B','SVC-ELK-006','異常耗電檢測','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-006-C','SVC-ELK-006','異常耗電檢測','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-007-A','SVC-ELK-007','馬達異常檢測','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-007-B','SVC-ELK-007','馬達異常檢測','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-007-C','SVC-ELK-007','馬達異常檢測','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-008-A','SVC-ELK-008','管理者權限初始化','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-008-B','SVC-ELK-008','管理者權限初始化','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-008-C','SVC-ELK-008','管理者權限初始化','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-ELK-009-A','SVC-ELK-009','App 綁定 / Wi-Fi 設定到府協助','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-009-B','SVC-ELK-009','App 綁定 / Wi-Fi 設定到府協助','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-ELK-009-C','SVC-ELK-009','App 綁定 / Wi-Fi 設定到府協助','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-DOOR-001-A','SVC-DOOR-001','門片反弓調整','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-001-B','SVC-DOOR-001','門片反弓調整','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-001-C','SVC-DOOR-001','門片反弓調整','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-DOOR-002-A','SVC-DOOR-002','鉸鏈歪斜 / 門下沉調整','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-002-B','SVC-DOOR-002','鉸鏈歪斜 / 門下沉調整','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-002-C','SVC-DOOR-002','鉸鏈歪斜 / 門下沉調整','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-DOOR-003-A','SVC-DOOR-003','受口片 / 門框調整','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-003-B','SVC-DOOR-003','受口片 / 門框調整','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-003-C','SVC-DOOR-003','受口片 / 門框調整','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-DOOR-004-A','SVC-DOOR-004','鎖體位移 / 機械損傷處理','LV-A',400,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-004-B','SVC-DOOR-004','鎖體位移 / 機械損傷處理','LV-B',300,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-DOOR-004-C','SVC-DOOR-004','鎖體位移 / 機械損傷處理','LV-C',250,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-CAR-001-A','SVC-CAR-001','汽車開鎖','LV-A',1250,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-001-B','SVC-CAR-001','汽車開鎖','LV-B',1000,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-001-C','SVC-CAR-001','汽車開鎖','LV-C',850,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-CAR-002-A','SVC-CAR-002','機車開鎖','LV-A',1250,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-002-B','SVC-CAR-002','機車開鎖','LV-B',1000,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-002-C','SVC-CAR-002','機車開鎖','LV-C',850,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-CAR-003-A','SVC-CAR-003','汽車晶片鑰匙評估','LV-A',1250,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-003-B','SVC-CAR-003','汽車晶片鑰匙評估','LV-B',1000,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-003-C','SVC-CAR-003','汽車晶片鑰匙評估','LV-C',850,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review'),
  ('PAY-SVC-CAR-004-A','SVC-CAR-004','汽車遙控器評估','LV-A',1250,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-004-B','SVC-CAR-004','汽車遙控器評估','LV-B',1000,0.2,0.15,'TWD','2026-06-02',NULL,'draft'),
  ('PAY-SVC-CAR-004-C','SVC-CAR-004','汽車遙控器評估','LV-C',850,0.2,0.15,'TWD','2026-06-02',NULL,'draft_review')
ON CONFLICT (rule_id) DO NOTHING;
