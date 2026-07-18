"use client";

// CR-0118 平台 console —「租戶管理」頁。已開站租戶 registry 檢視 + 生命週期
// (平台層標示)。UAT W6-2:文案接 i18n(platform.tenants namespace)。

import TenantsPanel from "@/components/platform/TenantsPanel";
import { useTranslations } from "@/components/i18n/LocaleProvider";

export default function PlatformTenantsPage() {
  const t = useTranslations("platform.tenants");
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{t("subtitle")}</p>
      </div>
      <TenantsPanel />
    </div>
  );
}
