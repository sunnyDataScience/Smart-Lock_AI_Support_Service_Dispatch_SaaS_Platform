"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Check, Lock, RefreshCw, Edit3, KeyRound } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { ApiError, ApiErrorResponse, api, getCurrentSession } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";
import { RolePermissionsEditor } from "@/components/admin/RolePermissionsEditor";
import AdminResetPasswordModal from "@/components/admin/AdminResetPasswordModal";
import { useRealtimeChannel } from "@shared/hooks/useRealtimeChannel";

type Role = components["schemas"]["Role"];
type RolePermission = components["schemas"]["RolePermission"];
type RoleResource = components["schemas"]["RoleResource"];

interface RolesResponse {
  data?: Role[];
  message?: string;
}

// 階層（與後端 ROLE_HIERARCHY 對齊；前端僅用於 disable 編輯按鈕的 UX
// hint，最終授權仍在後端強制）。
const ROLE_HIERARCHY: Record<string, number> = {
  super_admin: 5,
  tenant_admin: 4,
  admin: 4,
  operations_director: 3,
  supervisor: 3, // 主管（CR-0111）
  accounting: 3, // 會計（CR-0111）
  operations_manager: 2,
  reviewer: 2,
  family_reviewer: 2, // 家族覆核員（CR-0111）
  customer_service: 1,
  support_agent: 1,
  dispatcher: 1,
  dispatch_officer: 1,
  technician: 1,
  brand_oem: 0,
  distributor: 0, // 經銷/門市/建商（CR-0111）
  auditor: 0,
  line_user: 0,
};

const RBAC_ADMIN_ROLES = new Set(["admin", "tenant_admin", "super_admin"]);

function PermCell({
  granted,
  locked,
}: {
  granted: boolean;
  locked: boolean;
}) {
  if (granted && locked) {
    return (
      <div className="flex items-center justify-center gap-1">
        <div className="flex h-5 w-5 items-center justify-center rounded bg-[#94A3B8]">
          <Check className="h-3 w-3 text-white" />
        </div>
        <Lock className="h-3 w-3 text-[var(--text-disabled)]" />
      </div>
    );
  }
  if (granted) {
    return (
      <div className="flex h-5 w-5 items-center justify-center rounded bg-[var(--primary)]">
        <Check className="h-3 w-3 text-white" />
      </div>
    );
  }
  if (locked) {
    return (
      <div className="flex items-center justify-center gap-1">
        <div className="h-5 w-5 rounded border border-[var(--border)] bg-[var(--bg-page)]" />
        <Lock className="h-3 w-3 text-[var(--text-disabled)]" />
      </div>
    );
  }
  return (
    <div className="h-5 w-5 rounded border border-[var(--border)] bg-[var(--bg-surface)]" />
  );
}

export default function RolesPage() {
  const t = useTranslations("admin.roles");
  const tc = useTranslations("admin.common");
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Role | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [actorRole, setActorRole] = useState<string | null>(null);
  const [resetOpen, setResetOpen] = useState(false);

  const resourceLabels = useMemo<Record<RoleResource, string>>(
    () => ({
      work_orders: t("resource.work_orders"),
      technicians: t("resource.technicians"),
      customers: t("resource.customers"),
      accounting: t("resource.accounting"),
      invoices: t("resource.invoices"),
      refunds: t("resource.refunds"),
      inventory: t("resource.inventory"),
      warranty: t("resource.warranty"),
      disputes: t("resource.disputes"),
      audit_logs: t("resource.audit_logs"),
      roles: t("resource.roles"),
      system_settings: t("resource.system_settings"),
    }),
    [t],
  );

  async function fetchRoles() {
    setLoading(true);
    setError(null);
    try {
      // 已遷移至 tenant-scoped v2 端點（CR-0002-α）；legacy /api/v1/roles 仍雙掛但帶 Deprecation header，P4 Stage 7 可刪。
      const session = getCurrentSession();
      const tenantId = session?.tenantId;
      if (!tenantId) {
        throw new ApiError(400, {
          error_code: "NO_TENANT",
          message: "缺少 tenant，請重新登入",
        } as ApiErrorResponse);
      }
      const res = await api.get<RolesResponse>(
        `/tenants/${encodeURIComponent(tenantId)}/rbac/roles`,
      );
      const items = res.data ?? [];
      setRoles(items);
      if (items.length > 0 && selectedId === null) {
        // 預設選「第一個可編輯的角色」（階層低於當前使用者），
        // 否則編輯鈕一進來就是灰的、看起來像壞掉（CR-0111）。
        const session = getCurrentSession();
        const actorTier = ROLE_HIERARCHY[session?.role ?? ""] ?? 0;
        const firstEditable = items.find(
          (r) => (ROLE_HIERARCHY[r.id] ?? 0) < actorTier,
        );
        setSelectedId((firstEditable ?? items[0]).id);
      }
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchRoles();
    const session = getCurrentSession();
    setActorRole(session?.role ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 訂閱 /realtime/rbac — 任何權限變更 → 重抓 roles 即時刷新矩陣
  // （RbacChangedBanner 會獨立處理「需要重新整理」的全域提示）
  useRealtimeChannel<{ role_id?: string; changed_codes?: string[] }>({
    channelPath: "/realtime/rbac",
    onMessage: () => {
      void fetchRoles();
    },
  });

  const activeRole = useMemo(
    () =>
      roles.find((r) => r.id === selectedId) ??
      (roles.length > 0 ? roles[0] : null),
    [roles, selectedId],
  );

  const canEdit = useMemo(() => {
    if (!actorRole || !RBAC_ADMIN_ROLES.has(actorRole)) return false;
    if (!activeRole) return false;
    const actorTier = ROLE_HIERARCHY[actorRole] ?? 0;
    const targetTier = ROLE_HIERARCHY[activeRole.id] ?? 0;
    return actorTier > targetTier;
  }, [actorRole, activeRole]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchRoles}
                disabled={loading}
                title={tc("refresh")}
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${
                    loading ? "animate-spin" : ""
                  }`}
                />
              </button>
              {actorRole && RBAC_ADMIN_ROLES.has(actorRole) && (
                <button
                  onClick={() => setResetOpen(true)}
                  title="管理員代為重設使用者密碼"
                  className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-[10px] hover:bg-[var(--bg-page)]"
                >
                  <KeyRound className="h-4 w-4 text-[var(--text-secondary)]" />
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    重設使用者密碼
                  </span>
                </button>
              )}
              <button
                disabled
                title={t("createCustomTooltip")}
                className="flex cursor-not-allowed items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-[10px] opacity-50"
              >
                <Plus className="h-4 w-4 text-white" />
                <span className="text-sm font-medium text-white">
                  {t("createCustom")}
                </span>
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {toast && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {toast}
            </div>
          )}

          {/* Role Cards */}
          {loading && roles.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              {t("loadingRoles")}
            </div>
          ) : roles.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              {t("noRoles")}
            </div>
          ) : (
            <div className="grid grid-cols-5 gap-4">
              {roles.map((role) => {
                const isSelected = (selectedId ?? roles[0]?.id) === role.id;
                return (
                  <button
                    key={role.id}
                    onClick={() => setSelectedId(role.id)}
                    className={`flex flex-col gap-3 rounded-xl p-4 text-left ${
                      isSelected
                        ? "border-2 border-[var(--primary)] bg-[var(--bg-surface)] shadow-[0_2px_8px_rgba(37,99,235,0.13)]"
                        : "border border-[var(--border)] bg-[var(--bg-surface)]"
                    }`}
                  >
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="text-base font-semibold text-[var(--text-primary)]">
                        {role.name}
                      </span>
                      {role.is_system && (
                        <span className="rounded-md bg-[#DBEAFE] px-2 py-[3px] text-[11px] font-semibold text-[var(--primary)]">
                          {t("systemBadge")}
                        </span>
                      )}
                    </div>
                    <span className="line-clamp-2 text-[12px] leading-snug text-[var(--text-secondary)]">
                      {role.description}
                    </span>
                    <span className="w-fit rounded-md bg-[#F1F5F9] px-2 py-1 text-xs font-medium text-[var(--text-secondary)]">
                      {t("userCount", { count: role.user_count })}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Permission Matrix */}
          {activeRole && (
            <div className="flex min-h-[620px] flex-1 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <span className="text-base font-semibold text-[var(--text-primary)]">
                    {t("matrixTitle", { name: activeRole.name })}
                  </span>
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {t("matrixHint")}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setEditing(activeRole)}
                    disabled={!canEdit}
                    data-testid="edit-permissions-btn"
                    title={
                      canEdit
                        ? t("editPermissions")
                        : actorRole && !RBAC_ADMIN_ROLES.has(actorRole)
                          ? t("editTooltipNoRbac")
                          : t("editTooltipNoTier")
                    }
                    className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-[14px] py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Edit3 className="h-4 w-4" />
                    <span className="text-[13px] font-medium">
                      {t("editPermissions")}
                    </span>
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-auto">
                <div className="flex items-center border-b border-[var(--border)] bg-[#F8FAFC] px-5 py-[10px]">
                  <div className="w-[200px]">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {t("cols.resource")}
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {t("cols.read")}
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {t("cols.write")}
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {t("cols.approve")}
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {t("cols.delete")}
                    </span>
                  </div>
                </div>

                {activeRole.permissions.map((row: RolePermission) => (
                  <div
                    key={row.resource}
                    className="flex items-center border-b border-[var(--border)] px-5 py-2"
                  >
                    <div className="w-[200px]">
                      <span className="text-[13px] font-medium text-[var(--text-primary)]">
                        {resourceLabels[row.resource] ?? row.resource}
                      </span>
                    </div>
                    <div className="flex flex-1 items-center justify-center">
                      <PermCell granted={row.read} locked={!!row.locked} />
                    </div>
                    <div className="flex flex-1 items-center justify-center">
                      <PermCell granted={row.write} locked={!!row.locked} />
                    </div>
                    <div className="flex flex-1 items-center justify-center">
                      <PermCell granted={!!row.approve} locked={!!row.locked} />
                    </div>
                    <div className="flex flex-1 items-center justify-center">
                      <PermCell granted={row.delete} locked={!!row.locked} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {editing && (
        <RolePermissionsEditor
          role={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            setToast(t("savedToast", { name: editing.name }));
            void fetchRoles();
            setTimeout(() => setToast(null), 4000);
          }}
        />
      )}

      {resetOpen && (
        <AdminResetPasswordModal onClose={() => setResetOpen(false)} />
      )}
    </div>
  );
}
