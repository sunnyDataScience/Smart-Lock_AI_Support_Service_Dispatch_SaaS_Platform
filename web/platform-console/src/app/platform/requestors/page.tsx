"use client";

// CR-0114 收尾 — 平台 console「發案方審核」。
// 品牌申請(導入意向)與廠商帳號(發案登入帳號)都是「發案的一方」(相對於師傅=
// 接案方),業主指示合成同一頁。兩者資料模型與審核動作不同(品牌申請核准要填代號
// + 出開站指引;廠商核准是啟用帳號)→ 用分頁分隔,不硬混成一張清單。
// UAT W6-2:文案接 i18n(platform.requestors namespace)。

import { useState } from "react";
import BrandApplicationsPanel from "@/components/platform/BrandApplicationsPanel";
import VendorsPanel from "@/components/platform/VendorsPanel";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type Tab = "applications" | "vendors";

const TABS: { value: Tab; key: string }[] = [
  { value: "applications", key: "tabApplications" },
  { value: "vendors", key: "tabVendors" },
];

export default function RequestorsReviewPage() {
  const t = useTranslations("platform.requestors");
  const [tab, setTab] = useState<Tab>("applications");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{t("subtitle")}</p>
      </div>

      {/* 分頁切換 */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((item) => {
          const active = tab === item.value;
          return (
            <button
              key={item.value}
              type="button"
              onClick={() => setTab(item.value)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
                active
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {t(item.key)}
            </button>
          );
        })}
      </div>

      {tab === "applications" ? <BrandApplicationsPanel /> : <VendorsPanel />}
    </div>
  );
}
