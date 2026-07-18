"use client";

import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

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
  emptyText,
}: {
  title: string;
  rows: Array<{ label: string; count: number }>;
  labelKey: string;
  emptyText: string;
}) {
  return (
    <div className="flex flex-1 flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
      <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">{title}</h3>
      {rows.length === 0 ? (
        <span className="py-4 text-center text-[13px] text-[var(--text-secondary)]">
          {emptyText}
        </span>
      ) : (
        <ol className="flex flex-col gap-2">
          {rows.map((r, i) => (
            <li
              key={`${labelKey}-${r.label}-${i}`}
              className="flex items-center justify-between rounded-md px-2 py-1 hover:bg-[var(--bg-page)]"
            >
              <span className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#EFF6FF] text-[11px] font-semibold text-[var(--primary)]">
                  {i + 1}
                </span>
                <span className="text-[13px] text-[var(--text-primary)]">{r.label}</span>
              </span>
              <span className="font-mono text-[13px] font-medium text-[var(--text-secondary)]">
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
  // UAT W6-1：區塊標題接 i18n（pages.dashboard.charts）
  const t = useTranslations("pages.dashboard.charts");
  const topicRows = hotTopics
    .filter((x) => x.topic && typeof x.count === "number")
    .map((x) => ({ label: x.topic as string, count: x.count as number }));
  const brandRows = topBrands
    .filter((b) => b.brand && typeof b.count === "number")
    .map((b) => ({ label: b.brand as string, count: b.count as number }));

  return (
    // UAT W6-4：小螢幕堆疊、sm 以上並排
    <div className="flex flex-col gap-6 sm:flex-row">
      <RankList
        title={t("hotTopics")}
        rows={topicRows}
        labelKey="topic"
        emptyText={t("noData")}
      />
      <RankList
        title={t("topBrands")}
        rows={brandRows}
        labelKey="brand"
        emptyText={t("noData")}
      />
    </div>
  );
}
