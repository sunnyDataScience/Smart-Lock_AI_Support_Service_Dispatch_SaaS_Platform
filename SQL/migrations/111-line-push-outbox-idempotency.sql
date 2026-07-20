-- 111-line-push-outbox-idempotency.sql
-- CR-0175 R13/R19：客戶推播 outbox 冪等（enqueue 去重）
--
-- 背景：line_push_outbox 的 enqueue 為無條件 INSERT，(reference_id, push_kind) 無唯一約束，
--   上游重入 → 兩筆 pending row → worker 各推一次 → 客戶收重複推播（R13）。
--
-- 業主裁決（2026-07-20，CR-0175 §8 問題 1/2）：per-kind 白名單。
--   🔒 事件型、不可重複 → 納入 partial unique（擋重複 enqueue）：
--        work_order_assigned / work_order_accepted / work_order_document / scope_change_result
--   🔓 可更新後再推 → 不納入唯一（允許合法重推）：
--        quote_proposal / reschedule_proposal / scope_change_proposal / schedule_conflict
--   dedup 視窗 = status <> 'dead'（dead 後允許重試新 row）。
--   （worker 端 x_line_retry_key（CR-0175 C）另對「所有」kind 擋 crash-replay 重送。）
--
-- 性質：forward-only、idempotent（先清存量重複 → CREATE UNIQUE INDEX IF NOT EXISTS）。

BEGIN;

-- 1) 清理存量重複：僅 strict 白名單 + reference_id NOT NULL + status<>'dead'，
--    保留 (created_at, id) 最大者、刪其餘，確保 partial unique index 可建立。
--    （乾淨庫 = 刪 0 列；(created_at,id) 全序 tie-break 避免同 created_at 撞。）
DELETE FROM line_push_outbox a
USING line_push_outbox b
WHERE a.reference_id IS NOT NULL
  AND a.status <> 'dead'
  AND a.push_kind IN (
      'work_order_assigned', 'work_order_accepted',
      'work_order_document', 'scope_change_result')
  AND b.reference_id = a.reference_id
  AND b.push_kind = a.push_kind
  AND b.status <> 'dead'
  AND (b.created_at, b.id) > (a.created_at, a.id);

-- 2) partial unique index：strict kind 於 dedup 視窗（status<>'dead'）內
--    (reference_id, push_kind) 唯一。enqueue 端以相同 predicate 做 ON CONFLICT DO NOTHING。
CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_ref_kind_strict
    ON line_push_outbox (reference_id, push_kind)
    WHERE reference_id IS NOT NULL
      AND status <> 'dead'
      AND push_kind IN (
          'work_order_assigned', 'work_order_accepted',
          'work_order_document', 'scope_change_result');

COMMENT ON INDEX uq_outbox_ref_kind_strict IS
    'CR-0175: 事件型 push_kind 於 dedup 視窗(status<>dead)內 (reference_id,push_kind) 唯一，擋重複 enqueue';

COMMIT;
