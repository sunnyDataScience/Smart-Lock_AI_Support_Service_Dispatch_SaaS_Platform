"use client";

import Link from "next/link";
import { skillTitle, skillDesc } from "@/lib/skill-labels";
import {
  STATUS_LABEL,
  SOURCE_LABEL,
  type SkillSummary,
  type SkillStatus,
  type SkillSource,
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

// #11 來源徽章:原本裸灰字與相鄰的狀態徽章視覺語言不一致(難看)。
// 改為與 StatusBadge 同形狀的 pill,靠 stroke SVG 圖示區分三種來源;
// 色彩刻意克制(統一中性底/邊框,不搶狀態徽章的紅綠黃語意色)——來源是
// 輔助資訊,一眼靠「形狀一致 + 圖示」辨識即可。
const SOURCE_ICON: Record<SkillSource, string> = {
  // package box:平台出廠範本
  factory_seed:
    "m7.5 4.27 9 5.15M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z M3.3 7 12 12l8.7-5 M12 22V12",
  // zap:pipeline 自動汲取
  pipeline_ingest:
    "M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z",
  // pencil:品牌人工編輯
  brand_edit: "M12 20h9 M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z",
};

function SourceBadge({ source }: { source: SkillSource }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--bg-page)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-3 w-3 shrink-0 text-[var(--text-tertiary)]"
        aria-hidden
      >
        <path d={SOURCE_ICON[source]} />
      </svg>
      {SOURCE_LABEL[source]}
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
              <td className="px-4 py-3">
                <SourceBadge source={s.latest_source} />
              </td>
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
