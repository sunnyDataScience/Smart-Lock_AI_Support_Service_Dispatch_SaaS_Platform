"use client";

import {
  Lock,
  LayoutDashboard,
  MessageSquare,
  ClipboardList,
  BookOpen,
  Truck,
  Users,
  CircleUserRound,
  Receipt,
  Package,
  BarChart3,
  ShieldCheck,
  Settings,
  LogOut,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentSession, logout, type CurrentSession } from "@/lib/api";

interface NavChild {
  label: string;
  href: string;
}

interface NavItem {
  icon: React.ElementType;
  label: string;
  href: string;
  children?: NavChild[];
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: "儀表板", href: "/dashboard" },
  { icon: MessageSquare, label: "對話管理", href: "/conversations" },
  { icon: ClipboardList, label: "問題卡", href: "/problem-cards" },
  {
    icon: BookOpen,
    label: "知識庫",
    href: "/knowledge-base/cases",
    children: [
      { label: "案例庫", href: "/knowledge-base/cases" },
      { label: "手冊管理", href: "/knowledge-base/manuals" },
      { label: "SOP 審核", href: "/knowledge-base/sop-drafts" },
    ],
  },
  {
    icon: Truck,
    label: "派工管理",
    href: "/work-orders",
    children: [
      { label: "工單列表", href: "/work-orders" },
      { label: "派工佇列監控", href: "/admin/dispatch-queue" },
    ],
  },
  { icon: Users, label: "技師管理", href: "/technicians" },
  { icon: CircleUserRound, label: "客戶主檔", href: "/admin/customers" },
  {
    icon: Receipt,
    label: "帳務與結算",
    href: "/accounting",
    children: [
      { label: "月結算總覽", href: "/accounting" },
      { label: "退款審批", href: "/admin/refunds" },
      { label: "保固索賠", href: "/admin/warranty-claims" },
      { label: "爭議仲裁", href: "/admin/disputes" },
    ],
  },
  { icon: Package, label: "庫存", href: "/admin/inventory" },
  {
    icon: BarChart3,
    label: "報表中心",
    href: "/admin/reports/kpi",
    children: [
      { label: "KPI 儀表板", href: "/admin/reports/kpi" },
      { label: "技師排行", href: "/admin/reports/technician-ranking" },
      { label: "營收報表", href: "/admin/reports/revenue" },
      { label: "SOP 績效", href: "/admin/knowledge-base/sop-performance" },
    ],
  },
  {
    icon: ShieldCheck,
    label: "稽核與權限",
    href: "/admin/audit-events",
    children: [
      { label: "RBAC 管理", href: "/admin/roles" },
      { label: "稽核日誌", href: "/admin/audit-events" },
    ],
  },
  { icon: Settings, label: "系統設定", href: "/settings" },
];

function isParentActive(item: NavItem, pathname: string): boolean {
  if (item.children?.some((child) => pathname.startsWith(child.href))) {
    return true;
  }
  return pathname.startsWith(item.href);
}

function isChildActive(child: NavChild, pathname: string): boolean {
  return pathname === child.href || pathname.startsWith(child.href + "/");
}

const ROLE_LABELS: Record<string, string> = {
  admin: "系統管理員",
  reviewer: "審核員",
  technician: "技師",
  brand_oem: "品牌 OEM",
  line_user: "LINE 使用者",
};

function displayName(session: CurrentSession | null): string {
  if (!session) return "—";
  if (session.email) {
    const at = session.email.indexOf("@");
    return at > 0 ? session.email.slice(0, at) : session.email;
  }
  if (session.userId) return `User ${session.userId.slice(0, 6)}`;
  return "—";
}

function avatarChar(session: CurrentSession | null): string {
  if (!session) return "?";
  if (session.email) return session.email[0].toUpperCase();
  if (session.userId) return session.userId[0].toUpperCase();
  return "?";
}

function roleLabel(session: CurrentSession | null): string {
  if (!session?.role) return "—";
  return ROLE_LABELS[session.role] ?? session.role;
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const [session, setSession] = useState<CurrentSession | null>(null);

  useEffect(() => {
    setSession(getCurrentSession());
  }, []);

  async function onLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  }

  return (
    <aside className="flex w-[240px] flex-col bg-[var(--bg-sidebar)]">
      <div className="flex items-center gap-3 p-5">
        <Lock className="h-7 w-7 text-[var(--primary)]" />
        <span className="text-lg font-bold text-white">SmartLock</span>
      </div>

      <nav className="flex flex-1 flex-col gap-[2px] overflow-y-auto px-3 py-2">
        {navItems.map((item) => {
          const active = isParentActive(item, pathname);
          return (
            <div key={item.href + item.label}>
              <Link
                href={item.href}
                className={`flex items-center gap-3 rounded-lg py-[10px] text-sm ${
                  active
                    ? "border-l-[3px] border-[var(--primary)] bg-[#1E3A5F] pl-[9px] pr-3 font-semibold"
                    : "px-3 font-medium text-[var(--text-disabled)]"
                }`}
              >
                <item.icon
                  className={`h-5 w-5 shrink-0 ${
                    active ? "text-[var(--primary)]" : ""
                  }`}
                />
                <span className={active ? "text-[var(--text-inverse)]" : ""}>
                  {item.label}
                </span>
              </Link>
              {active && item.children && (
                <div className="flex flex-col gap-[2px] py-1 pl-[44px]">
                  {item.children.map((child) => {
                    const childActive = isChildActive(child, pathname);
                    return (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={`rounded-[6px] px-3 py-[6px] text-sm ${
                          childActive
                            ? "bg-[#1E3A5F] font-semibold text-[#93C5FD]"
                            : "font-normal text-[var(--text-disabled)]"
                        }`}
                      >
                        {child.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="flex items-center gap-3 border-t border-[#334155] px-5 py-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-sm font-semibold text-white">
          {avatarChar(session)}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
          <span
            className="truncate text-sm font-medium text-white"
            title={session?.email ?? session?.userId ?? "未登入"}
          >
            {displayName(session)}
          </span>
          <span className="text-xs text-[var(--text-disabled)]">
            {roleLabel(session)}
          </span>
        </div>
        <button
          type="button"
          onClick={onLogout}
          disabled={loggingOut}
          title="登出"
          aria-label="登出"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[var(--text-disabled)] transition hover:bg-[#334155] hover:text-white disabled:opacity-50"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
