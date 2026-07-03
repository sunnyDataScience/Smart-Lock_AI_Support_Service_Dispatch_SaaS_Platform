"use client";

import { ArrowRight, Building2, Lock, Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { auth } from "@/lib/api";
import { APP_MODE, PEER_PORTAL_URL } from "@/lib/appMode";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 多角色平台 landing。20260702 會議決議 2:入口從 3-4 個濃縮為兩條 ——
// 「品牌/經銷/鎖店登錄」(派案方 → 後台管理系統)與「鎖匠師傅登錄」(接案方 →
// 師傅工作台),登入與註冊在各入口內同框(仿 Google),不再有獨立註冊入口。
// `/` 已加入 AuthGuard PUBLIC_PATHS(公開頁);已登入者頂部顯示「進入後台」捷徑。

type Entry = {
  href: string;
  icon: typeof Building2;
  titleKey: string;
  descKey: string;
};

// CR-0112 雙 stack:dispatch build 的師傅入口指向對方 portal(有配 PEER 時);
// tech build 的 landing 直接導 /tech-login(見下方 useEffect),不渲染雙卡。
const TECH_ENTRY_HREF =
  APP_MODE === "dispatch" && PEER_PORTAL_URL
    ? `${PEER_PORTAL_URL}/tech-login`
    : "/tech-login";

const ENTRIES: Entry[] = [
  { href: "/login", icon: Building2, titleKey: "dispatcherTitle", descKey: "dispatcherDesc" },
  { href: TECH_ENTRY_HREF, icon: Wrench, titleKey: "techTitle", descKey: "techDesc" },
];

export default function Home() {
  const t = useTranslations("landing");
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  // tech build:師傅 stack 只有一條入口,landing 直接進 /tech-login。
  useEffect(() => {
    if (APP_MODE === "tech") router.replace("/tech-login");
  }, [router]);

  // token 只能在 client 讀（localStorage）；已登入者給「進入後台」捷徑，但不自動跳轉，
  // 讓 landing 永遠可見可測。
  useEffect(() => {
    setAuthed(Boolean(auth.getAccessToken()));
  }, []);

  if (APP_MODE === "tech") return null;

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-[var(--bg-page)] px-4 py-12">
      <div className="absolute right-4 top-4 flex items-center gap-2">
        <LocaleToggle />
        <ThemeToggle />
      </div>

      <main className="flex w-full max-w-[760px] flex-col items-center">
        {/* 品牌標頭 */}
        <div className="mb-10 flex flex-col items-center gap-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--primary)] shadow-sm">
            <Lock className="h-7 w-7 text-white" />
          </div>
          <div className="flex flex-col items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)]">
              SmartLock
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">{t("tagline")}</p>
          </div>

          {authed ? (
            <Link
              href="/dashboard"
              className="mt-2 inline-flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white transition hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2"
            >
              {t("enterBackend")}
              <ArrowRight className="h-4 w-4" />
            </Link>
          ) : (
            <p className="mt-1 text-[13px] font-medium text-[var(--text-secondary)]">
              {t("subtitle")}
            </p>
          )}
        </div>

        {/* 角色入口卡片 */}
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2">
          {ENTRIES.map(({ href, icon: Icon, titleKey, descKey }) => (
            <Link
              key={href}
              href={href}
              className="group flex items-center gap-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-sm transition hover:border-[var(--border-focus)] hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2"
            >
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--bg-page)] text-[var(--primary)] transition group-hover:bg-[var(--primary)] group-hover:text-white">
                <Icon className="h-5 w-5" />
              </div>
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="text-sm font-semibold text-[var(--text-primary)]">
                  {t(titleKey)}
                </span>
                <span className="truncate text-[13px] text-[var(--text-secondary)]">
                  {t(descKey)}
                </span>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-[var(--text-disabled)] transition group-hover:translate-x-0.5 group-hover:text-[var(--primary)]" />
            </Link>
          ))}
        </div>

        <p className="mt-10 text-center text-xs text-[var(--text-disabled)]">
          {t("footer")}
        </p>
      </main>
    </div>
  );
}
