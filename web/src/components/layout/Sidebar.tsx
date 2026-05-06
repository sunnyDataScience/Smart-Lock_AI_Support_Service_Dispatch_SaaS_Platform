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
import NotificationBell from "./NotificationBell";
import Hamburger from "./Hamburger";
import { useSidebar } from "./SidebarContext";

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
      { label: "家族覆核", href: "/knowledge-base/family-reviews" },
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
      { label: "會計傳票", href: "/accounting/vouchers" },
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
      { label: "情緒告警", href: "/admin/sentiment-alerts" },
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
  const { isOpen, isMobile, close } = useSidebar();
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
    <>
      {/* Mobile floating hamburger — 任何 page 不論用不用 <Header /> 都有 */}
      <Hamburger />

      {/* Mobile backdrop — 半透明遮罩，點擊關閉 drawer
       * md:hidden 在桌機自動隱藏，避免依賴 JS isMobile 判斷的 SSR 不一致 */}
      {isOpen && (
        <div
          onClick={close}
          aria-hidden="true"
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
        />
      )}
      <aside
        id="sidebar-drawer"
        aria-label="主導航"
        aria-hidden={isMobile && !isOpen ? true : undefined}
        /* 行動版預設：fixed 浮層 + 隱藏（-translate-x-full）
         * 桌機（md+）：relative + 永遠顯示（md:translate-x-0 覆蓋）
         * isOpen：行動版加 translate-x-0 滑入 */
        className={`fixed inset-y-0 left-0 z-40 flex h-full w-[240px] flex-col bg-[var(--bg-sidebar)] transition-transform duration-200 ease-out md:relative md:inset-auto md:z-auto md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
      <div className="flex items-center gap-3 p-5">
        <Lock className="h-7 w-7 text-[var(--primary)]" aria-hidden="true" />
        <span className="text-lg font-bold text-white">SmartLock</span>
      </div>

      <nav
        className="flex flex-1 flex-col gap-[2px] overflow-y-auto px-3 py-2"
        aria-label="頁面導航"
      >
        {navItems.map((item) => {
          const active = isParentActive(item, pathname);
          const hasChildren = !!item.children;
          const submenuId = hasChildren ? `submenu-${item.href.replace(/\//g, "-")}` : undefined;
          return (
            <div key={item.href + item.label}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                aria-haspopup={hasChildren ? "menu" : undefined}
                aria-expanded={hasChildren ? active : undefined}
                aria-controls={hasChildren && active ? submenuId : undefined}
                className={`flex items-center gap-3 rounded-lg py-[10px] text-sm focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-sidebar)] ${
                  active
                    ? "border-l-[3px] border-[var(--primary)] bg-[#1E3A5F] pl-[9px] pr-3 font-semibold"
                    : "px-3 font-medium text-[var(--text-disabled)]"
                }`}
              >
                <item.icon
                  className={`h-5 w-5 shrink-0 ${
                    active ? "text-[var(--primary)]" : ""
                  }`}
                  aria-hidden="true"
                />
                <span className={active ? "text-[var(--text-inverse)]" : ""}>
                  {item.label}
                </span>
              </Link>
              {active && hasChildren && (
                <ul
                  id={submenuId}
                  role="menu"
                  aria-label={`${item.label} 子選單`}
                  className="flex flex-col gap-[2px] py-1 pl-[44px]"
                >
                  {item.children!.map((child) => {
                    const childActive = isChildActive(child, pathname);
                    return (
                      <li key={child.href} role="none">
                        <Link
                          href={child.href}
                          role="menuitem"
                          aria-current={childActive ? "page" : undefined}
                          className={`block rounded-[6px] px-3 py-[6px] text-sm focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--bg-sidebar)] ${
                            childActive
                              ? "bg-[#1E3A5F] font-semibold text-[#93C5FD]"
                              : "font-normal text-[var(--text-disabled)]"
                          }`}
                        >
                          {child.label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
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
        <NotificationBell variant="dark" />
        <button
          type="button"
          onClick={onLogout}
          disabled={loggingOut}
          title="登出"
          aria-label={loggingOut ? "正在登出" : "登出"}
          aria-busy={loggingOut}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-[var(--text-disabled)] transition hover:bg-[#334155] hover:text-white focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-sidebar)] disabled:opacity-50"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      </aside>
    </>
  );
}
