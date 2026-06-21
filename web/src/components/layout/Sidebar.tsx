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
  Store,
  Tag,
  FileText,
  Banknote,
  Receipt,
  Package,
  BarChart3,
  ShieldCheck,
  Settings,
  AlertTriangle,
  LogOut,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentSession, logout, type CurrentSession } from "@/lib/api";
import { canAccessRoute } from "@/lib/rolePolicy";
import NotificationBell from "./NotificationBell";
import Hamburger from "./Hamburger";
import { useSidebar } from "./SidebarContext";
import { useTranslations } from "@/components/i18n/LocaleProvider";

interface NavChild {
  /** translation key under sidebar.nav.*; e.g. "kbCases" → t("kbCases") */
  id: string;
  href: string;
}

interface NavItem {
  icon: React.ElementType;
  /** translation key under sidebar.nav.*; e.g. "dashboard" → t("dashboard") */
  id: string;
  href: string;
  children?: NavChild[];
}

// id 對應 messages/{locale}.json 的 sidebar.nav.* 鍵
const navItems: NavItem[] = [
  { icon: LayoutDashboard, id: "dashboard", href: "/dashboard" },
  { icon: MessageSquare, id: "conversations", href: "/conversations" },
  { icon: ClipboardList, id: "problemCards", href: "/problem-cards" },
  {
    icon: BookOpen,
    id: "knowledgeBase",
    href: "/knowledge-base/cases",
    children: [
      { id: "kbCases", href: "/knowledge-base/cases" },
      { id: "kbManuals", href: "/knowledge-base/manuals" },
      { id: "kbSopDrafts", href: "/knowledge-base/sop-drafts" },
      { id: "kbFamilyReviews", href: "/knowledge-base/family-reviews" },
    ],
  },
  {
    icon: Truck,
    id: "dispatch",
    href: "/work-orders",
    children: [
      { id: "workOrders", href: "/work-orders" },
      { id: "dispatchQueue", href: "/admin/dispatch-queue" },
      { id: "materialRequests", href: "/admin/material-requests" },
    ],
  },
  { icon: Users, id: "technicians", href: "/technicians" },
  { icon: AlertTriangle, id: "exceptions", href: "/admin/exceptions" },
  { icon: Store, id: "vendorApprovals", href: "/admin/vendor-approvals" },
  { icon: Tag, id: "quoteCatalog", href: "/admin/quote-catalog" },
  { icon: FileText, id: "quotes", href: "/admin/quotes" },
  { icon: Banknote, id: "payoutRules", href: "/admin/payout-rules" },
  { icon: CircleUserRound, id: "customers", href: "/admin/customers" },
  {
    icon: Receipt,
    id: "accounting",
    href: "/accounting",
    children: [
      { id: "settlements", href: "/accounting" },
      { id: "vouchers", href: "/accounting/vouchers" },
      { id: "refunds", href: "/admin/refunds" },
      { id: "warranty", href: "/admin/warranty-claims" },
      { id: "disputes", href: "/admin/disputes" },
    ],
  },
  { icon: Package, id: "inventory", href: "/admin/inventory" },
  {
    icon: BarChart3,
    id: "reports",
    href: "/admin/reports/kpi",
    children: [
      { id: "kpi", href: "/admin/reports/kpi" },
      { id: "techRanking", href: "/admin/reports/technician-ranking" },
      { id: "revenue", href: "/admin/reports/revenue" },
      { id: "sopPerformance", href: "/admin/knowledge-base/sop-performance" },
    ],
  },
  {
    icon: ShieldCheck,
    id: "audit",
    href: "/admin/audit-events",
    children: [
      { id: "roles", href: "/admin/roles" },
      { id: "staff", href: "/admin/staff" },
      { id: "auditLogs", href: "/admin/audit-events" },
      { id: "sentimentAlerts", href: "/admin/sentiment-alerts" },
    ],
  },
  { icon: Settings, id: "settings", href: "/settings" },
];

function isParentActive(item: NavItem, pathname: string): boolean {
  if (item.children?.some((child) => pathname.startsWith(child.href))) {
    return true;
  }
  return pathname.startsWith(item.href);
}

function isChildActive(
  child: NavChild,
  pathname: string,
  siblings: NavChild[],
): boolean {
  if (pathname === child.href) return true;
  if (!pathname.startsWith(child.href + "/")) return false;
  // 前綴命中（深層子路由）：若有更精確（href 更長）的 sibling 也命中，
  // 讓那個 sibling 亮，本項不亮 —— 避免區段根頁（如 /accounting）把
  // 子頁（/accounting/vouchers）一起點亮造成雙亮。
  return !siblings.some(
    (s) =>
      s.href.length > child.href.length &&
      (pathname === s.href || pathname.startsWith(s.href + "/")),
  );
}

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

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isOpen, isMobile, close } = useSidebar();
  const tSidebar = useTranslations("sidebar");
  const tNav = useTranslations("sidebar.nav");
  const tRole = useTranslations("role");
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

  function roleLabel(): string {
    if (!session?.role) return "—";
    return tRole(session.role);
  }

  // CR-0021：依角色過濾 nav（父項可存取、或有任一可見子項才顯示）。
  const role = session?.role ?? null;
  const visibleNavItems = navItems
    .map((item) => ({
      ...item,
      children: item.children?.filter((c) => canAccessRoute(c.href, role)),
    }))
    .filter(
      (item) =>
        canAccessRoute(item.href, role) || (item.children?.length ?? 0) > 0,
    );

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
        aria-label={tSidebar("navAria")}
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
        <span className="text-lg font-bold text-white">
          {tSidebar("appName")}
        </span>
      </div>

      <nav
        className="flex flex-1 flex-col gap-[2px] overflow-y-auto px-3 py-2"
        aria-label={tSidebar("pageNavAria")}
      >
        {visibleNavItems.map((item) => {
          const active = isParentActive(item, pathname);
          const hasChildren = !!item.children;
          const submenuId = hasChildren ? `submenu-${item.href.replace(/\//g, "-")}` : undefined;
          const itemLabel = tNav(item.id);
          return (
            <div key={item.href + item.id}>
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
                  {itemLabel}
                </span>
              </Link>
              {active && hasChildren && (
                <ul
                  id={submenuId}
                  role="menu"
                  aria-label={tSidebar("submenuLabel", { label: itemLabel })}
                  className="flex flex-col gap-[2px] py-1 pl-[44px]"
                >
                  {item.children!.map((child) => {
                    const childActive = isChildActive(child, pathname, item.children!);
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
                          {tNav(child.id)}
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
            title={session?.email ?? session?.userId ?? tSidebar("loggedOut")}
          >
            {displayName(session)}
          </span>
          <span className="text-xs text-[var(--text-disabled)]">
            {roleLabel()}
          </span>
        </div>
        <NotificationBell variant="dark" />
        <button
          type="button"
          onClick={onLogout}
          disabled={loggingOut}
          title={tSidebar("logout")}
          aria-label={loggingOut ? tSidebar("loggingOut") : tSidebar("logout")}
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
