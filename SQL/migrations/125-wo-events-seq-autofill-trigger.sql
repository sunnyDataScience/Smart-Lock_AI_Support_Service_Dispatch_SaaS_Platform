-- ============================================================================
-- 125-wo-events-seq-autofill-trigger.sql  —— CR-0193 補強（部署安全）
-- ============================================================================
-- WHY（實際踩到的事故，記下來以免重蹈）：
--   122 給 `work_order_events.seq` 加了 NOT NULL，並要求所有寫入走
--   `work_order_service._insert_wo_event` 取號。這在「migration 先於 code」的
--   部署順序下是對的——但**只有在 code 隨後立刻上線時才成立**。
--
--   2026-07-30 prod 實際發生：122 套用成功後，code 部署被 pre-flight 擋下
--   （CR-0190 的 SERVICE_CREDENTIAL_PEPPER secret 未建、migrations 120/121 未套），
--   於是 prod 停在「新 schema ＋ 舊 code」的中間狀態。舊 code 的 12 條 INSERT
--   都不給 seq → assign / reassign / reject / arrival / door_check 全數
--   NotNullViolation。實測確認（交易內 INSERT 後 rollback）。
--
--   教訓：**「migration 先於 code」的前提是 code 一定跟得上**。當 code 部署可能
--   被別的原因阻擋時，schema 變更必須對舊 code 保持相容——否則 migration 本身
--   就是一次故障。
--
-- WHAT：BEFORE INSERT trigger，`seq IS NULL` 時自動補 per-工單連號。
--   - 舊 code（不給 seq）→ trigger 補號，行為與新 code 一致
--   - 新 code（`_insert_wo_event` 已算好 seq）→ 有值就不動，維持原邏輯與重試語意
--   - `NOT NULL` 與 `UNIQUE(work_order_id, seq)` 都保留，不變式不放寬
--
--   附帶好處：這使得「繞過唯一出口直接 INSERT」不再產生連號缺口，比原本只靠
--   NOT NULL 擋下更好——原設計是 fail loud，現在是 fail safe 且仍然連號。
--
-- ⚠️ 併發：trigger 內用 `MAX(seq)+1`，與 service 層同樣靠 UNIQUE 擋碰撞。
--   trigger 拋出的 unique violation 會傳回呼叫端；service 層已有重試，
--   舊 code 沒有重試（但舊 code 本來也沒有，且同工單併發寫事件極少見）。
-- ============================================================================

CREATE OR REPLACE FUNCTION public.wo_events_fill_seq()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.seq IS NULL THEN
        SELECT COALESCE(MAX(seq), 0) + 1 INTO NEW.seq
        FROM public.work_order_events
        WHERE work_order_id = NEW.work_order_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.wo_events_fill_seq() IS
    'CR-0193/125：seq 未給時自動補 per-工單連號。存在理由是「新 schema + 舊 code」'
    '的部署中間狀態必須可用（2026-07-30 prod 實際踩到）。新 code 自行取號時不受影響。';

DROP TRIGGER IF EXISTS trg_wo_events_fill_seq ON public.work_order_events;
CREATE TRIGGER trg_wo_events_fill_seq
    BEFORE INSERT ON public.work_order_events
    FOR EACH ROW
    EXECUTE FUNCTION public.wo_events_fill_seq();
