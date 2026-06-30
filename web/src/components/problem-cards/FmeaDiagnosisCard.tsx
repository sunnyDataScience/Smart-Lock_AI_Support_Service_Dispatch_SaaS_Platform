"use client";

// FMEA 分層信心診斷引擎為已刪的 Belief-Augmented ReAct 殘影、後端無實作，且 spec 01
// (M20 AI Ops)明令「不做 AI auto diagnosis」——詳見
// docs/_audit/diagnosis-engine-doc-trace-20260625.md（source-of-truth 衝突待業主裁決）。
// 原本寫死的「離合器」假診斷鏈已移除，改誠實空狀態，避免 demo 誤導成「AI 已完成診斷」。
export default function FmeaDiagnosisCard() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex flex-col gap-3">
        <div>
          <h2 className="text-[18px] font-bold text-[var(--text-primary)]">
            FMEA 診斷推理鏈
          </h2>
          <p className="text-[13px] text-[var(--text-secondary)]">
            症狀 → 故障 → 失效模式 → 缺陷 四層推理過程
          </p>
        </div>
        <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)]">
          <span className="text-[13px] text-[var(--text-disabled)]">
            尚未產生 FMEA 診斷鏈（診斷引擎未啟用）
          </span>
        </div>
      </div>
    </div>
  );
}
