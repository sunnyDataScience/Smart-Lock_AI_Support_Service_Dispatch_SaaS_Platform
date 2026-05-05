"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Map as MapIcon, ClipboardList, Wallet } from "lucide-react";

const TABS = [
  { label: "案件池", href: "/pool", Icon: MapIcon, match: /^\/pool/ },
  {
    label: "我的工單",
    href: "/my-orders",
    Icon: ClipboardList,
    match: /^\/my-orders/,
  },
  { label: "帳戶", href: "/account", Icon: Wallet, match: /^\/account/ },
];

export default function TechBottomNav() {
  const pathname = usePathname() ?? "";
  return (
    <nav className="sticky bottom-0 z-30 grid grid-cols-3 border-t border-[var(--border)] bg-white pb-[env(safe-area-inset-bottom,0)]">
      {TABS.map(({ label, href, Icon, match }) => {
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
