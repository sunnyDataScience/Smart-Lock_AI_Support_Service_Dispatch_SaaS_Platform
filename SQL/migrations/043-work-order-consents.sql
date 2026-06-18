-- 043-work-order-consents.sql
--
-- WHY（CR-0033 S3 / 20260617 gap-audit + 藍圖模組 4「施工免責與合規」）：
--   現況：appearance_change_consents 只針對門外觀；無通用 work_order_consents；
--   免責條款文字零存儲、客戶版電子工單 PDF 無免責段（CR-0026 §8-Q3 defer 至此）。
--   藍圖模組 4：三段固定免責（新機安裝開孔噪音 / 破壞鎖費用自負 / 個資授權）需客戶同意。
--
-- WHAT：
--   work_order_consents 通用同意紀錄表：三段 consent_type + accepted + accepted_at +
--   text_version（文本版本快照，§8-Q5 工單記當時版本）+ ip_address（不可否認性留痕）。
--   UNIQUE(work_order_id, consent_type) → 同一工單同段重複提交為 upsert（冪等）。
--
-- 性質：DB schema（新表，向後相容，全 IF NOT EXISTS 可重套）。法務佔位 first；
--   三段文本以 service 常數存（非 legal_text_versions 版本主檔，避免過度設計）。

CREATE TABLE IF NOT EXISTS work_order_consents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id   UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    consent_type    VARCHAR(30) NOT NULL,  -- new_installation / lock_destruction / personal_data
    accepted        BOOLEAN NOT NULL DEFAULT FALSE,
    accepted_at     TIMESTAMP WITH TIME ZONE,
    text_version    VARCHAR(50) NOT NULL DEFAULT 'blueprint-draft-2026-06',
    ip_address      VARCHAR(64),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (work_order_id, consent_type)
);

CREATE INDEX IF NOT EXISTS idx_wo_consents_work_order ON work_order_consents(work_order_id);

COMMENT ON TABLE work_order_consents IS 'CR-0033 三段施工免責同意紀錄（藍圖模組 4）；文本版本快照 + IP 留痕；UNIQUE(work_order_id, consent_type) 冪等 upsert';
COMMENT ON COLUMN work_order_consents.consent_type IS 'new_installation（新機安裝）/ lock_destruction（破壞鎖）/ personal_data（個資授權）';
COMMENT ON COLUMN work_order_consents.text_version IS '同意當下的免責文本版本（待法務定稿後升版）；正式措辭見 consent_service.CONSENT_TEXTS';
