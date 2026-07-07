"use client";

// CR-0118 平台 console —「租戶管理」頁。已開站租戶 registry 檢視 + 生命週期
// (平台層標示)。內部工具,文案直接繁中。

import TenantsPanel from "@/components/platform/TenantsPanel";

export default function PlatformTenantsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">租戶管理</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          所有已開站的品牌租戶(核准品牌申請後自動登錄)。平台方跨品牌名冊與生命週期標示。
        </p>
      </div>
      <TenantsPanel />
    </div>
  );
}
