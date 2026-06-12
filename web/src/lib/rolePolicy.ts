/**
 * rolePolicy.ts — 前端 route → role 存取政策（CR-0021 §8 Q3）。
 *
 * 單一真相源：AuthGuard（route gate）與 Sidebar（nav 過濾）共用。
 * 以「能否載入頁面」為 gate;唯讀差異（如 cs 看工單）由後端 role_required 把關。
 *
 * 原則：
 *   - admin / tenant_admin / super_admin → 全放行（避免誤擋管理員）。
 *   - 未列到的路由 → 預設放行（demo 安全;敏感頁已明列，如 /accounting /admin/roles）。
 *   - 對應表對齊後端 role_required 守衛（前端不比後端寬/嚴，避免 confusing UX）。
 */

const FULL_ACCESS_ROLES = new Set(["admin", "tenant_admin", "super_admin"]);

const ALL_BACKOFFICE = [
  "admin",
  "operations_manager",
  "dispatcher",
  "customer_service",
];

/** 路由 prefix → 允許角色。longest-prefix-wins。 */
const ROUTE_POLICY: { prefix: string; roles: string[] }[] = [
  { prefix: "/dashboard", roles: ALL_BACKOFFICE },
  { prefix: "/conversations", roles: ALL_BACKOFFICE },
  { prefix: "/problem-cards", roles: ALL_BACKOFFICE },
  { prefix: "/notifications", roles: ALL_BACKOFFICE },
  { prefix: "/settings", roles: ALL_BACKOFFICE },
  { prefix: "/knowledge-base", roles: ["admin", "operations_manager", "customer_service"] },
  // 工單列表：cs 唯讀（後端把關）→ 可載入
  { prefix: "/work-orders", roles: ALL_BACKOFFICE },
  { prefix: "/admin/dispatch-queue", roles: ["admin", "operations_manager", "dispatcher"] },
  { prefix: "/admin/dispatch-manual", roles: ["admin", "operations_manager", "dispatcher"] },
  { prefix: "/admin/material-requests", roles: ["admin", "operations_manager", "dispatcher"] },
  { prefix: "/technicians", roles: ["admin", "operations_manager", "dispatcher"] },
  { prefix: "/admin/customers", roles: ["admin", "operations_manager", "customer_service"] },
  { prefix: "/accounting", roles: ["admin", "operations_manager"] },
  { prefix: "/admin/refunds", roles: ["admin", "operations_manager"] },
  { prefix: "/admin/warranty-claims", roles: ["admin", "operations_manager"] },
  { prefix: "/admin/disputes", roles: ["admin", "operations_manager"] },
  { prefix: "/admin/inventory", roles: ["admin", "operations_manager"] },
  { prefix: "/admin/reports", roles: ["admin", "operations_manager"] },
  { prefix: "/admin/knowledge-base", roles: ["admin", "operations_manager"] },
  { prefix: "/admin/roles", roles: ["admin"] },
  { prefix: "/admin/audit-events", roles: ["admin"] },
  // catch-all：其餘 /admin/* → admin / ops
  { prefix: "/admin", roles: ["admin", "operations_manager"] },
];

/** 該角色是否可存取此路由。role 為 null（無 JWT role）時放行（token 檢查另在 AuthGuard）。 */
export function canAccessRoute(pathname: string, role: string | null): boolean {
  if (!role || FULL_ACCESS_ROLES.has(role)) return true;
  const matches = ROUTE_POLICY.filter(
    (p) => pathname === p.prefix || pathname.startsWith(p.prefix + "/"),
  ).sort((a, b) => b.prefix.length - a.prefix.length);
  if (matches.length === 0) return true; // 未列到 → 放行
  return matches[0].roles.includes(role);
}
