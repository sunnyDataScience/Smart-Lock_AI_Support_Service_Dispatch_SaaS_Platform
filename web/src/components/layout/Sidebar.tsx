"use client";

import {
  Lock,
  LayoutDashboard,
  MessageSquare,
  FileText,
  ClipboardList,
  Wrench,
  Wallet,
  Settings,
  BookOpen,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  icon: React.ElementType;
  label: string;
  href: string;
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: "儀表板", href: "/dashboard" },
  { icon: MessageSquare, label: "對話管理", href: "/conversations" },
  { icon: FileText, label: "問題卡片", href: "/problem-cards" },
  { icon: ClipboardList, label: "工單管理", href: "/work-orders" },
  { icon: Wrench, label: "技師管理", href: "/technicians" },
  { icon: Wallet, label: "財務管理", href: "/accounting" },
  { icon: Settings, label: "設備管理", href: "/settings" },
  { icon: BookOpen, label: "知識庫管理", href: "/knowledge-base" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-[240px] flex-col bg-[var(--bg-sidebar)]">
      <div className="flex items-center gap-3 p-5">
        <Lock className="h-7 w-7 text-[var(--primary)]" />
        <span className="text-lg font-bold text-white">SmartLock</span>
      </div>

      <nav className="flex flex-1 flex-col gap-[2px] px-3 py-2">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg py-[10px] text-sm ${
                isActive
                  ? "border-l-[3px] border-[var(--primary)] bg-[#1E3A5F] pl-[9px] pr-3 font-semibold"
                  : "px-3 font-medium text-[var(--text-disabled)]"
              }`}
            >
              <item.icon
                className={`h-5 w-5 shrink-0 ${
                  isActive ? "text-[var(--primary)]" : ""
                }`}
              />
              <span className={isActive ? "text-[var(--text-inverse)]" : ""}>
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="flex items-center gap-3 border-t border-[#334155] px-5 py-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-sm font-semibold text-white">
          王
        </div>
        <div className="flex flex-col gap-[2px]">
          <span className="text-sm font-medium text-white">王小明</span>
          <span className="text-xs text-[var(--text-disabled)]">
            主管理員
          </span>
        </div>
      </div>
    </aside>
  );
}
