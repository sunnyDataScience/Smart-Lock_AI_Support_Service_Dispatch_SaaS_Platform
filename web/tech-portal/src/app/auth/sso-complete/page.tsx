"use client";

// SSO cookie-only 落地頁：token 已由 server callback 寫 HttpOnly cookie。

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { bootstrapSession } from "@/lib/api";
import { fallbackRouteForRole } from "@/lib/rolePolicy";

export default function SsoCompletePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void bootstrapSession().then((session) => {
      if (!session) {
        setError("SSO session 建立失敗，請重新登入");
        return;
      }
      router.replace(fallbackRouteForRole(session.role));
    });
  }, [router]);

  return (
    <div className="flex min-h-dvh items-center justify-center text-sm text-[var(--text-secondary)]">
      {error ? (
        <div className="text-center">
          <p className="mb-3 text-red-600">{error}</p>
          <button onClick={() => router.replace("/tech-login")}
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
