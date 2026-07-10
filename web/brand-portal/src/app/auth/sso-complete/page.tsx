"use client";

// SSO 過渡落地頁(CR-0146):從 fragment 取 token 存 localStorage(既有前端
// 體系依賴;ACT-01 退場=R3),再依角色導向落點。fragment 不會被送往 server。

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth, getCurrentSession } from "@/lib/api";
import { fallbackRouteForRole } from "@/lib/rolePolicy";

export default function SsoCompletePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const access = params.get("access_token");
    if (!access) {
      setError("SSO 回應缺 token,請重新登入");
      return;
    }
    auth.setTokens(access, params.get("refresh_token") ?? "");
    const session = getCurrentSession();
    if (session?.tenantId) auth.setTenantId(session.tenantId);
    // 清 fragment 避免殘留於歷史紀錄
    window.history.replaceState(null, "", "/auth/sso-complete");
    router.replace(fallbackRouteForRole(session?.role ?? null));
  }, [router]);

  return (
    <div className="flex min-h-dvh items-center justify-center text-sm text-[var(--text-secondary)]">
      {error ? (
        <div className="text-center">
          <p className="mb-3 text-red-600">{error}</p>
          <button onClick={() => router.replace("/login")}
                  className="rounded-md bg-[var(--primary)] px-4 py-2 text-white">
            回登入頁
          </button>
        </div>
      ) : (
        "SSO 登入完成,導向中…"
      )}
    </div>
  );
}
