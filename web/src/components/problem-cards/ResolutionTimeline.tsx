"use client";

// 解決嘗試歷程（L1/L2/L3 + 信心分數）為已刪的 Belief-Augmented ReAct 殘影、後端無真實
// attempts 資料（problem_cards.attempts=[]、confidence_score 硬寫 None）——詳見
// docs/_audit/diagnosis-engine-doc-trace-20260625.md。原寫死的 L1 45%/L2 78%/L3 92%
// 假信心（每張卡都一樣）已移除，改誠實空狀態。
export default function ResolutionTimeline() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
        解決嘗試歷程
      </h2>
      <div className="mt-4 flex h-24 items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)]">
        <span className="text-[13px] text-[var(--text-disabled)]">
          尚無解決嘗試紀錄（診斷引擎未啟用）
        </span>
      </div>
    </div>
  );
}
