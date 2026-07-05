"use client";

// CR-0114 平台 console 儀表板(R1 骨架)。
// R2/R3 接上品牌申請/師傅申請後,此頁加 pending 計數卡與捷徑。

import { useEffect, useState } from "react";
import { Building2, UserCheck } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface PlatformMe {
  data: {
    id: string;
    display_name: string | null;
    email: string;
  };
}

export default function PlatformDashboardPage() {
  const [me, setMe] = useState<PlatformMe["data"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<PlatformMe>("/api/v1/platform/me")
      .then((res) => {
        if (!cancelled) setMe(res.data);
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">儀表板</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          {me
            ? `${me.display_name || me.email}，歡迎回來。`
            : error ?? "載入中…"}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--primary-subtle,rgba(59,130,246,0.12))]">
              <Building2 className="h-5 w-5 text-[var(--primary)]" aria-hidden />
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--text-primary)]">品牌申請</p>
              <p className="text-xs text-[var(--text-secondary)]">
                品牌廠商鎖店的平台使用申請（下一輪接上）
              </p>
            </div>
          </div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--primary-subtle,rgba(59,130,246,0.12))]">
              <UserCheck className="h-5 w-5 text-[var(--primary)]" aria-hidden />
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--text-primary)]">師傅申請</p>
              <p className="text-xs text-[var(--text-secondary)]">
                鎖匠師傅的註冊審核與生命週期管理（下一輪接上）
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
