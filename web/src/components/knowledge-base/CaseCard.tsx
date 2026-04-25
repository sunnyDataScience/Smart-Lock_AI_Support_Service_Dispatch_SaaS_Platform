"use client";

interface CaseCardProps {
  id: string;
  title: string;
  brand: string;
  model?: string;
  accuracy: number;
  usageCount: number;
  updatedAt: string;
}

function getProgressColor(accuracy: number): string {
  if (accuracy >= 80) return "var(--status-success)";
  if (accuracy >= 50) return "var(--accent)";
  return "var(--status-danger)";
}

export default function CaseCard({
  title,
  brand,
  model,
  accuracy,
  usageCount,
  updatedAt,
}: CaseCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-sm">
      <h3 className="text-[15px] font-bold leading-snug text-[var(--text-primary)]">
        {title}
      </h3>

      <div className="flex gap-2">
        <span className="rounded bg-[#EFF6FF] px-[10px] py-1 text-xs font-medium text-[var(--primary)]">
          {brand}
        </span>
        {model && (
          <span className="rounded bg-[#EFF6FF] px-[10px] py-1 text-xs font-medium text-[var(--primary)]">
            {model}
          </span>
        )}
      </div>

      <div className="flex items-center gap-[10px]">
        <div className="h-2 flex-1 overflow-hidden rounded bg-[var(--border)]">
          <div
            className="h-full rounded"
            style={{
              width: `${accuracy}%`,
              backgroundColor: getProgressColor(accuracy),
            }}
          />
        </div>
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          {accuracy}%
        </span>
      </div>

      <div className="flex items-center justify-between gap-[10px]">
        <span className="rounded bg-[var(--secondary)] px-[10px] py-1 text-[11px] font-medium text-white">
          已使用 {usageCount} 次
        </span>
        <span className="text-xs text-[var(--text-secondary)]">
          更新於 {updatedAt}
        </span>
      </div>
    </div>
  );
}
