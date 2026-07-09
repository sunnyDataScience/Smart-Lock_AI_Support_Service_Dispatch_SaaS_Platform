"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMemo } from "react";
import {
  Home,
  Map as MapIcon,
  ClipboardList,
  User,
  LogOut,
  KeyRound,
} from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { auth, logout } from "@/lib/api";

/**
 * TechSidebar — 桌面（≥768px）常駐左側導覽，對標後台 Sidebar.tsx。
 * 手機隱藏（改由 TechBottomNav 取代）。usePathname 高亮當前頁。
 * 與 TechBottomNav 共用同一組四項導覽（首頁 / 案件池 / 我的工單 / 帳戶）。
 */
export default function TechSidebar() {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const t = useTranslations("techPortal.shell");

  const items = useMemo(
    () => [
      { label: t("bottomNav.home"), href: "/home", Icon: Home, match: /^\/home/ },
      { label: t("bottomNav.pool"), href: "/pool", Icon: MapIcon, match: /^\/pool/ },
      {
        label: t("bottomNav.myOrders"),
        href: "/my-orders",
        Icon: ClipboardList,
        match: /^\/my-orders/,
      },
      { label: t("bottomNav.account"), href: "/account", Icon: User, match: /^\/account/ },
    ],
    [t],
  );

  async function handleLogout() {
    if (typeof window !== "undefined" && !window.confirm(t("sidebar.logoutConfirm"))) {
      return;
    }
    try {
      await logout();
    } catch {
      auth.clear();
    } finally {
      router.replace("/tech-login");
    }
  }

  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col overflow-y-auto border-r border-[var(--border)] bg-[var(--bg-surface)] md:flex">
      {/* brand */}
      <div className="flex h-16 items-center gap-2 border-b border-[var(--border)] px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--primary)]">
          <KeyRound className="h-5 w-5 text-white" />
        </div>
        <div className="flex flex-col">
          <span className="text-[14px] font-bold leading-tight text-[var(--text-primary)]">
            {t("sidebar.brandName")}
          </span>
          <span className="text-[11px] text-[var(--text-secondary)]">
            {t("sidebar.subtitle")}
          </span>
        </div>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>

      {/* nav */}
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {items.map(({ label, href, Icon, match }) => {
          const active = match.test(pathname);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-full px-4 py-2.5 text-[14px] font-medium transition ${
                active
                  ? "bg-[var(--primary-light)] text-[var(--primary)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              }`}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* logout */}
      <div className="border-t border-[var(--border)] p-3">
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-full px-4 py-2.5 text-[14px] font-medium text-red-600 transition hover:bg-red-50"
        >
          <LogOut className="h-5 w-5" />
          {t("sidebar.logout")}
        </button>
      </div>
    </aside>
  );
}
