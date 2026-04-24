"use client";

import {
  Lock,
  LayoutDashboard,
  MessageSquare,
  CreditCard,
  ClipboardList,
  Wrench,
  BookOpen,
  Settings,
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
  { icon: CreditCard, label: "問題卡片", href: "/problem-cards" },
  { icon: ClipboardList, label: "工單管理", href: "/work-orders" },
  { icon: Wrench, label: "技師管理", href: "/technicians" },
  { icon: BookOpen, label: "知識庫", href: "/knowledge-base" },
  { icon: Settings, label: "系統設定", href: "/settings" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-[240px] flex-col bg-[var(--bg-sidebar)]">
      <div className="flex items-center gap-[10px] border-b border-white/10 px-6 py-6">
        <Lock className="h-[22px] w-[22px] text-white" />
        <span className="text-[18px] font-bold text-white">SmartLock</span>
      </div>

      <nav className="flex flex-1 flex-col gap-[2px] px-0 py-4">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-[10px] text-[14px] ${
                isActive
                  ? "border-l-[3px] border-[var(--primary)] bg-white/8 pl-[13px] font-semibold text-white"
                  : "pl-[19px] font-medium text-[var(--text-disabled)]"
              }`}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10" />

      <div className="flex items-center gap-3 px-6 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--primary)] text-[14px] font-semibold text-white">
          王
        </div>
        <div className="flex flex-col gap-[2px]">
          <span className="text-[13px] font-medium text-white">王小明</span>
          <span className="text-[11px] text-[var(--text-disabled)]">
            系統管理員
          </span>
        </div>
      </div>
    </aside>
  );
}
