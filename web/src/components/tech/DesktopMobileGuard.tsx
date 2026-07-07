"use client";

import { useEffect, useState } from "react";
import { Smartphone } from "lucide-react";
import BackToHome from "@/components/layout/BackToHome";
import { useTranslations } from "@/components/i18n/LocaleProvider";

const MOBILE_BREAKPOINT = 768; // 寬度 ≥ 769px 視為桌面

/**
 * 技師端 PWA 為純 mobile 設計，桌面瀏覽器訪問時提示改用手機。
 * 開發/測試需要在桌面驗證時，可加 query `?force_desktop=1` 強制顯示頁面。
 */
export default function DesktopMobileGuard({
  children,
}: {
  children: React.ReactNode;
}) {
  const t = useTranslations("techPortal.shell.guard");
  const [isDesktop, setIsDesktop] = useState(false);
  const [forceDesktop, setForceDesktop] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("force_desktop") === "1") {
      try {
        sessionStorage.setItem("force_desktop", "1");
      } catch {
        // ignore
      }
    }
    try {
      if (sessionStorage.getItem("force_desktop") === "1") {
        setForceDesktop(true);
      }
    } catch {
      // ignore
    }

    const mq = window.matchMedia(`(min-width: ${MOBILE_BREAKPOINT + 1}px)`);
    setIsDesktop(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  if (isDesktop && !forceDesktop) {
    const currentUrl =
      typeof window !== "undefined" ? window.location.href : "";
    // QR Code 用 chart api 簡易產生（無依賴）；可後續改用 client-side qrcode lib
    const qrSrc = currentUrl
      ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(currentUrl)}`
      : "";
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-4">
        <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-8 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--primary)]/10">
            <Smartphone className="h-7 w-7 text-[var(--primary)]" />
          </div>
          <h1 className="text-[18px] font-bold text-[var(--text-primary)]">
            {t("openOnPhone")}
          </h1>
          <p className="text-center text-[13px] leading-[1.6] text-[var(--text-secondary)]">
            {t("description")}
          </p>

          {qrSrc && (
            <div className="mt-2 flex flex-col items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] p-4">
              <img
                src={qrSrc}
                alt={t("qrAlt")}
                className="h-[180px] w-[180px] rounded-md"
              />
              <span className="text-[11px] text-[var(--text-disabled)]">
                {t("scanHint")}
              </span>
            </div>
          )}

          <div className="mt-2 w-full border-t border-[var(--border)] pt-4 text-center text-[11px] text-[var(--text-disabled)]">
            {t("devCheckHint")}
            <button
              type="button"
              onClick={() => {
                try {
                  sessionStorage.setItem("force_desktop", "1");
                } catch {
                  // ignore
                }
                setForceDesktop(true);
              }}
              className="ml-1 text-[var(--primary)] hover:underline"
            >
              {t("forceDesktop")}
            </button>
          </div>

          <BackToHome className="mt-1" />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
