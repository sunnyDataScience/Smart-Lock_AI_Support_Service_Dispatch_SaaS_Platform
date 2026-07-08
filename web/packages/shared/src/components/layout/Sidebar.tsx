"use client";

import {
  Lock,
  LayoutDashboard,
  Inbox,
  MessageSquare,
  ClipboardList,
  BookOpen,
  Truck,
  CircleUserRound,
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
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getCurrentSession, logout, type CurrentSession } from "@shared/lib/api";
import { canAccessRoute } from "@shared/lib/rolePolicy";
import { UAT_HIDE_FAKE_FLOWS } from "@shared/lib/uatFlags";
import NotificationBell from "./NotificationBell";
import Hamburger from "./Hamburger";
import { useSidebar } from "./SidebarContext";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

// sidebar 捲軸位置持久化：Sidebar 在各頁各自掛載（非共用 layout），導航即 remount，
// 故用 sessionStorage 記住 nav 捲軸，remount 時於 paint 前還原，避免每次點選跳回頂端。
const SIDEBAR_SCROLL_KEY = "sidebar:scrollTop";
// SSR 安全：server 端無 layout effect，退回 useEffect 避免 hydration 警告。
const useIsoLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

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
  /**
   * 父項 active 判斷用的路徑前綴（可選）。當父項落地頁（href）只是區段內某一頁、
   * 但該區段還有其他頁（且不全部列為子項）時，用 matchPrefix 讓父項在整個區段內保持高亮。
   * 例：知識庫 href=/knowledge-base/cases，但 manuals/sop-drafts 也屬本區 → matchPrefix=/knowledge-base。
   */
  matchPrefix?: string;
}

interface NavSection {
  /** translation key under sidebar.section.*；分組標題 */
  titleId: string;
  items: NavItem[];
}

// 分組 + 排序依「開單流程」：進線 → 問題卡 → 開單 → 報價 → 派工 → 完工結算。
// 上半為日常開單流程主線，下半依序為審核例外／知識報表／設定主檔。
// id 對應 messages/{locale}.json 的 sidebar.nav.*；section titleId 對應 sidebar.section.*。
const navSections: NavSection[] = [
  {
    titleId: "operations",
    items: [
      { icon: LayoutDashboard, id: "dashboard", href: "/dashboard" },
      { icon: Inbox, id: "intakeCases", href: "/admin/cases" },
      { icon: MessageSquare, id: "conversations", href: "/conversations" },
      { icon: ClipboardList, id: "problemCards", href: "/problem-cards" },
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
      { icon: FileText, id: "quotes", href: "/admin/quotes" },
      { icon: CircleUserRound, id: "customers", href: "/admin/customers" },
      {
        icon: Receipt,
        id: "accounting",
        href: "/accounting",
        children: [
          { id: "settlements", href: "/accounting" },
          // UAT 隱藏(20260702 決議 7):退款審批為真狀態機但金流 0 接通,
          // 核准不會真的退錢 → 誤導性最高,UAT 期間整條入口移除。
          ...(UAT_HIDE_FAKE_FLOWS ? [] : [{ id: "refunds", href: "/admin/refunds" }]),
          { id: "warranty", href: "/admin/warranty-claims" },
          { id: "disputes", href: "/admin/disputes" },
        ],
      },
    ],
  },
  {
    titleId: "review",
    items: [
      { icon: AlertTriangle, id: "exceptions", href: "/admin/exceptions" },
    ],
  },
  {
    titleId: "insight",
    items: [
      {
        icon: BookOpen,
        id: "knowledgeBase",
        href: "/knowledge-base/cases",
        // 案例/手冊/SOP草稿已是知識庫頁內的分頁（tab bar），不在 sidebar 重複；
        // 僅保留非分頁的「家族覆核」。matchPrefix 讓父項在整個 /knowledge-base 區段保持高亮。
        matchPrefix: "/knowledge-base",
        children: [
          { id: "kbFamilyReviews", href: "/knowledge-base/family-reviews" },
        ],
      },
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
    ],
  },
  {
    titleId: "configuration",
    items: [
      { icon: Tag, id: "quoteCatalog", href: "/admin/quote-catalog" },
      { icon: Banknote, id: "payoutRules", href: "/admin/payout-rules" },
      { icon: Package, id: "inventory", href: "/admin/inventory" },
      {
        icon: ShieldCheck,
        id: "audit",
        href: "/admin/roles", // 父項點選導向角色管理（對齊「父 href = 第一個子項」慣例）
        children: [
          { id: "roles", href: "/admin/roles" },
          { id: "staff", href: "/admin/staff" },
          { id: "configGovernance", href: "/admin/config-governance" },
          { id: "auditLogs", href: "/admin/audit-events" },
          { id: "sentimentAlerts", href: "/admin/sentiment-alerts" },
        ],
      },
      { icon: Settings, id: "settings", href: "/settings" },
    ],
  },
];

function isParentActive(item: NavItem, pathname: string): boolean {
  if (item.matchPrefix && pathname.startsWith(item.matchPrefix)) {
    return true;
  }
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
  if (session.userId) return "使用者";
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
  const tSection = useTranslations("sidebar.section");
  const tRole = useTranslations("role");
  const [loggingOut, setLoggingOut] = useState(false);
  const [session, setSession] = useState<CurrentSession | null>(null);
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setSession(getCurrentSession());
  }, []);

  // 還原 nav 捲軸位置（remount 後、paint 前），避免導航跳回頂端
  useIsoLayoutEffect(() => {
    const el = navRef.current;
    if (!el) return;
    const saved = sessionStorage.getItem(SIDEBAR_SCROLL_KEY);
    if (saved) el.scrollTop = Number(saved) || 0;
  }, []);

  // 捲動時即時記住位置
  function persistNavScroll(e: React.UIEvent<HTMLElement>) {
    sessionStorage.setItem(SIDEBAR_SCROLL_KEY, String(e.currentTarget.scrollTop));
  }

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
  // 分組保留：先過濾各 section 的 items，整組無可見項則連標題一起移除。
  const role = session?.role ?? null;
  const visibleSections = navSections
    .map((section) => ({
      titleId: section.titleId,
      items: section.items
        .map((item) => ({
          ...item,
          children: item.children?.filter((c) => canAccessRoute(c.href, role)),
        }))
        .filter(
          (item) =>
            canAccessRoute(item.href, role) || (item.children?.length ?? 0) > 0,
        ),
    }))
    .filter((section) => section.items.length > 0);

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
        ref={navRef}
        onScroll={persistNavScroll}
        className="flex flex-1 flex-col gap-[2px] overflow-y-auto px-3 py-2"
        aria-label={tSidebar("pageNavAria")}
      >
        {visibleSections.map((section) => (
          <div key={section.titleId} className="flex flex-col gap-[2px]">
            <div className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-disabled)] opacity-60">
              {tSection(section.titleId)}
            </div>
            {section.items.map((item) => {
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
          </div>
        ))}
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
