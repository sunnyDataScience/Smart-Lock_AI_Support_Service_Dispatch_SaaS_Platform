"use client";

// CR-0114 平台方 console 殼(Lock AI 內部自用,非品牌/師傅面)。
// 刻意不用品牌後台 Sidebar:console 是跨品牌視角,選單極小(儀表板/師傅申請/
// 品牌申請),頂欄式即可。
// UAT W6-2(2026-07-18):原「內部工具不入 i18n」決策撤回——console 也要英文模式,
// 文案接 platform.* namespace,頂欄補 LocaleToggle(元件本已存在)。

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, LogOut, ShieldCheck } from "lucide-react";
import { logoutPlatformAdmin } from "@/lib/api";
import ThemeToggle from "@/components/theme/ThemeToggle";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

const NAV: { href: string; key: string }[] = [
  { href: "/platform", key: "dashboard" },
  { href: "/platform/requestors", key: "requestors" },
  { href: "/platform/technicians", key: "technicians" },
  { href: "/platform/tenants", key: "tenants" },
];

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations("platform.shell");

  // 登入頁與公開申請導入頁不套 console 殼(未登入 / 對外申請者面)
  if (pathname === "/platform/login" || pathname === "/platform/apply")
    return <>{children}</>;

  const onLogout = async () => {
    await logoutPlatformAdmin();
    router.replace("/platform/login");
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)]">
      <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--bg-surface)]">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]">
                <ShieldCheck className="h-4.5 w-4.5 text-white" aria-hidden />
              </div>
              <span className="text-sm font-bold text-[var(--text-primary)]">
                {t("brand")}
              </span>
            </div>
            <nav className="flex items-center gap-1" aria-label={t("navAria")}>
              {NAV.map((item) => {
                // 根路徑 /platform（儀表板）只精確比對 —— 否則 startsWith("/platform/")
                // 會對所有子頁成立,儀表板永遠亮。其餘項用「精確 or 前綴」(涵蓋 /[id] 詳情頁)。
                const active =
                  item.href === "/platform"
                    ? pathname === "/platform"
                    : pathname === item.href ||
                      pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-lg px-3 py-1.5 text-sm transition ${
                      active
                        ? "bg-[var(--primary-subtle,rgba(59,130,246,0.12))] font-semibold text-[var(--primary)]"
                        : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    {item.href === "/platform" && (
                      <LayoutDashboard className="mr-1.5 inline h-4 w-4 align-[-2px]" aria-hidden />
                    )}
                    {t(`nav.${item.key}`)}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-1">
            <LocaleToggle />
            <ThemeToggle />
            <button
              type="button"
              onClick={onLogout}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] hover:text-[var(--text-primary)]"
            >
              <LogOut className="h-4 w-4" aria-hidden />
              {t("logout")}
            </button>
          </div>
        </div>
      </header>
      {/* WCAG 2.4.1 Bypass Blocks：SkipLink.tsx 的 href="#main-content" 需要這個
          錨點才跳得到。tabIndex={-1} 不可省——沒有它 <main> 不可聚焦，skip link
          只會捲動而不移動鍵盤焦點，等於沒作用。 */}
      <main id="main-content" tabIndex={-1} className="mx-auto max-w-6xl px-4 py-8">
        {children}
      </main>
    </div>
  );
}
