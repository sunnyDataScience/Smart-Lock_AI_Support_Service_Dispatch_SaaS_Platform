"use client";

const PROGRESS_PERCENT = 80;
const RADIUS = 34;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const STROKE_DASHOFFSET = CIRCUMFERENCE * (1 - PROGRESS_PERCENT / 100);

export default function ProblemCardDetailSidebar() {
  return (
    <div className="flex w-[380px] flex-shrink-0 flex-col gap-4">
      {/* Status & Completeness */}
      <div className="flex w-full flex-col items-center gap-4 rounded-lg border border-[var(--border)] bg-white p-5">
        <div className="flex w-full items-center justify-between">
          <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
            狀態與完成度
          </span>
          <span className="rounded-full bg-[var(--status-danger)] px-3 py-1 text-[12px] font-semibold text-white">
            Escalated
          </span>
        </div>

        <div className="relative h-[80px] w-[80px]">
          <svg
            width="80"
            height="80"
            viewBox="0 0 80 80"
            className="-rotate-90"
          >
            <circle
              cx="40"
              cy="40"
              r={RADIUS}
              fill="none"
              stroke="#E2E8F0"
              strokeWidth="6"
            />
            <circle
              cx="40"
              cy="40"
              r={RADIUS}
              fill="none"
              stroke="var(--status-success)"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={STROKE_DASHOFFSET}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-[18px] font-bold text-[var(--text-primary)]">
            {PROGRESS_PERCENT}%
          </span>
        </div>

        <span className="text-[13px] font-medium text-[var(--text-secondary)]">
          {PROGRESS_PERCENT}% 完成度
        </span>
      </div>

      {/* Timestamps */}
      <div className="flex w-full flex-col gap-3 rounded-lg border border-[var(--border)] bg-white p-5">
        <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
          時間紀錄
        </span>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            建立時間
          </span>
          <span className="text-[13px] font-medium text-[var(--text-primary)]">
            2026-04-22 14:23
          </span>
        </div>
        <div className="flex items-start justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            最後更新
          </span>
          <div className="flex flex-col items-end gap-[2px]">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              2026-04-22 14:35
            </span>
            <span className="text-[11px] text-[var(--text-disabled)]">
              10分鐘前
            </span>
          </div>
        </div>
      </div>

      {/* Customer Info */}
      <div className="flex w-full flex-col gap-3 rounded-lg border border-[var(--border)] bg-white p-5">
        <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
          客戶資訊
        </span>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            客戶名稱
          </span>
          <span className="text-[13px] font-bold text-[var(--text-primary)]">
            陳小姐
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">電話</span>
          <span className="text-[13px] font-medium text-[var(--text-primary)]">
            0912-345-678
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            Email
          </span>
          <span className="text-[13px] font-medium text-[var(--text-primary)]">
            chen_mei@email.com
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            來源管道
          </span>
          <span className="rounded-full bg-[var(--status-success)] px-[10px] py-[3px] text-[11px] font-semibold text-white">
            LINE
          </span>
        </div>
      </div>

      {/* Linked Work Order */}
      <div className="flex w-full overflow-hidden rounded-lg border border-[var(--border)] bg-white">
        <div className="w-[3px] flex-shrink-0 bg-[var(--primary)]" />
        <div className="flex w-full flex-col gap-3 p-5">
          <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
            關聯工單
          </span>
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-secondary)]">
              工單編號
            </span>
            <span className="text-[13px] font-semibold text-[var(--primary)]">
              WO-20260422-001
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-secondary)]">
              工單狀態
            </span>
            <span className="rounded-full bg-[var(--status-assigned)] px-[10px] py-[3px] text-[11px] font-semibold text-white">
              已派工
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-secondary)]">
              指派技師
            </span>
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              李技師
            </span>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex w-full flex-col gap-2">
        <button
          type="button"
          className="w-full rounded-lg bg-[#94A3B8]/60 py-[10px] text-center text-[14px] font-semibold text-white"
        >
          標記已解決
        </button>
        <button
          type="button"
          className="w-full rounded-lg bg-[#94A3B8]/60 py-[10px] text-center text-[14px] font-semibold text-white"
        >
          升級至 L3 派工
        </button>
        <button
          type="button"
          className="w-full rounded-lg border-[1.5px] border-[var(--primary)] bg-transparent py-[10px] text-center text-[14px] font-semibold text-[var(--primary)]"
        >
          關聯知識案例
        </button>
      </div>
    </div>
  );
}
