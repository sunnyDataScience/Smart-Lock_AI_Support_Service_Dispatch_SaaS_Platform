"use client";

import Link from "next/link";
import { skillTitle, skillDesc } from "@/lib/skill-labels";
import {
  STATUS_LABEL,
  SOURCE_LABEL,
  type SkillSummary,
  type SkillStatus,
} from "@/lib/skills-api";

const STATUS_STYLE: Record<SkillStatus, string> = {
  published: "bg-[var(--success)]/12 text-[var(--success)] border-[var(--success)]/30",
  draft: "bg-[var(--warning)]/12 text-[var(--warning)] border-[var(--warning)]/30",
  retired: "bg-[var(--text-tertiary)]/12 text-[var(--text-tertiary)] border-[var(--border)]",
};

function StatusBadge({ status }: { status: SkillStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(
    d.getDate(),
  ).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

interface Props {
  items: SkillSummary[];
  loading: boolean;
}

export default function SkillsTable({ items, loading }: Props) {
  if (loading) {
    return (
      <div className="p-8 text-center text-sm text-[var(--text-secondary)]">載入中…</div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="mx-8 my-6 rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-surface)] p-10 text-center">
        <p className="text-sm text-[var(--text-secondary)]">
          尚無 AI 技能。技能定義了 AI 客服回答時依據的知識與話術。
        </p>
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
          可從出廠範本（客服 SOP、產品知識）調整，或新建品牌自有技能。
        </p>
      </div>
    );
  }

  return (
    <div className="mx-4 my-4 overflow-x-auto md:mx-8">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-4 py-3 font-medium">技能名稱</th>
            <th className="px-4 py-3 font-medium">發佈版本</th>
            <th className="px-4 py-3 font-medium">最新版本</th>
            <th className="px-4 py-3 font-medium">狀態</th>
            <th className="px-4 py-3 font-medium">來源</th>
            <th className="px-4 py-3 font-medium">更新時間</th>
            <th className="px-4 py-3 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr
              key={s.skill_name}
              className="border-b border-[var(--border)] transition-colors hover:bg-[var(--bg-page)]"
            >
              <td className="px-4 py-3">
                {/* #10 顯示層口語化:小編看人話標題,機器名保留小字(工程/除錯用) */}
                <div className="flex flex-col gap-0.5">
                  <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                    {skillTitle(s.skill_name)}
                  </span>
                  {skillDesc(s.skill_name) && (
                    <span className="text-[12px] text-[var(--text-secondary)]">
                      {skillDesc(s.skill_name)}
                    </span>
                  )}
                  <span className="font-mono text-[11px] text-[var(--text-tertiary)]">
                    {s.skill_name}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 tabular-nums text-[var(--text-secondary)]">
                {s.published_version != null ? (
                  <span className="font-medium text-[var(--text-primary)]">v{s.published_version}</span>
                ) : (
                  <span className="text-[var(--text-tertiary)]">未發佈</span>
                )}
              </td>
              <td className="px-4 py-3 tabular-nums text-[var(--text-secondary)]">v{s.latest_version}</td>
              <td className="px-4 py-3">
                <StatusBadge status={s.latest_status} />
              </td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">{SOURCE_LABEL[s.latest_source]}</td>
              <td className="px-4 py-3 tabular-nums text-xs text-[var(--text-tertiary)]">
                {fmtDate(s.updated_at)}
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  href={`/knowledge-base/skills/${encodeURIComponent(s.skill_name)}`}
                  className="text-sm font-medium text-[var(--primary)] hover:underline"
                >
                  編輯
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
