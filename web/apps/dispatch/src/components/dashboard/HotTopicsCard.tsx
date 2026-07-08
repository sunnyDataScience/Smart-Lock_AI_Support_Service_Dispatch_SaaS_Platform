"use client";

import type { components } from "@shared/types/api.generated";

type HotTopic = NonNullable<
  components["schemas"]["DashboardStats"]["hot_topics"]
>[number];
type TopBrand = NonNullable<
  components["schemas"]["DashboardStats"]["top_brands"]
>[number];

interface Props {
  hotTopics: HotTopic[];
  topBrands: TopBrand[];
}

function RankList({
  title,
  rows,
  labelKey,
}: {
  title: string;
  rows: Array<{ label: string; count: number }>;
  labelKey: string;
}) {
  return (
    <div className="flex flex-1 flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
      <h3 className="text-[14px] font-semibold text-[#18181B]">{title}</h3>
      {rows.length === 0 ? (
        <span className="py-4 text-center text-[13px] text-[var(--text-secondary)]">
          目前無資料
        </span>
      ) : (
        <ol className="flex flex-col gap-2">
          {rows.map((r, i) => (
            <li
              key={`${labelKey}-${r.label}-${i}`}
              className="flex items-center justify-between rounded-md px-2 py-1 hover:bg-[#F8FAFC]"
            >
              <span className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#EFF6FF] text-[11px] font-semibold text-[var(--primary)]">
                  {i + 1}
                </span>
                <span className="text-[13px] text-[#18181B]">{r.label}</span>
              </span>
              <span className="font-mono text-[13px] font-medium text-[#71717A]">
                {r.count}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function HotTopicsCard({ hotTopics, topBrands }: Props) {
  const topicRows = hotTopics
    .filter((t) => t.topic && typeof t.count === "number")
    .map((t) => ({ label: t.topic as string, count: t.count as number }));
  const brandRows = topBrands
    .filter((b) => b.brand && typeof b.count === "number")
    .map((b) => ({ label: b.brand as string, count: b.count as number }));

  return (
    <div className="flex gap-6">
      <RankList title="熱門問題類別" rows={topicRows} labelKey="topic" />
      <RankList title="熱門品牌" rows={brandRows} labelKey="brand" />
    </div>
  );
}
