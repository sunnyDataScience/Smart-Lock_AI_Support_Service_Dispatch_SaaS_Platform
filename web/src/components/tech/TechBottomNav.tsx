"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";
import { Home, Map as MapIcon, ClipboardList, User } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 手機（<768px）底部導覽；桌面（≥768px）由 TechSidebar 取代故 md:hidden。
export default function TechBottomNav() {
  const pathname = usePathname() ?? "";
  const t = useTranslations("techPortal.shell.bottomNav");

  const tabs = useMemo(
    () => [
      { label: t("home"), href: "/home", Icon: Home, match: /^\/home/ },
      { label: t("pool"), href: "/pool", Icon: MapIcon, match: /^\/pool/ },
      {
        label: t("myOrders"),
        href: "/my-orders",
        Icon: ClipboardList,
        match: /^\/my-orders/,
      },
      { label: t("account"), href: "/account", Icon: User, match: /^\/account/ },
    ],
    [t],
  );

  return (
    <nav className="sticky bottom-0 z-30 grid grid-cols-4 border-t border-[var(--border)] bg-white pb-[env(safe-area-inset-bottom,0)] md:hidden">
      {tabs.map(({ label, href, Icon, match }) => {
        const active = match.test(pathname);
        return (
          <Link
            key={href}
            href={href}
            className={`flex h-14 flex-col items-center justify-center gap-[2px] text-[11px] font-medium ${
              active ? "text-[var(--primary)]" : "text-[#94A3B8]"
            }`}
          >
            <Icon className="h-5 w-5" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
