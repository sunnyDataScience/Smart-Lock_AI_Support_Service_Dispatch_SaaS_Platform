"use client";

/**
 * RolePermissionsEditor — F-019 角色權限編輯 Modal
 *
 * Props:
 *   role     當前要編輯的 Role（含 permissions[] 已套用 overrides）
 *   onClose  按關閉 / Esc / 取消時呼叫
 *   onSaved  儲存成功後呼叫（caller 通常 refetch + toast）
 *
 * 邏輯：
 *   - 把 role.permissions 攤平成 desired set（resource.action）
 *   - 顯示 12 resource × 3 action grid，locked=true 的 cell 不可勾
 *   - 提交呼叫 PATCH /api/v1/roles/{role.id}/permissions
 *   - 後端 403 → 顯示「您的角色階層不足以授權此權限」
 *   - 後端 422 → 顯示具體 message
 */

import { useMemo, useState } from "react";
import { X, Loader2 } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type Role = components["schemas"]["Role"];
type RolePermission = components["schemas"]["RolePermission"];
type RoleResource = components["schemas"]["RoleResource"];

const RESOURCE_KEY: Record<RoleResource, string> = {
  work_orders: "resources.workOrders",
  technicians: "resources.technicians",
  customers: "resources.customers",
  accounting: "resources.accounting",
  invoices: "resources.invoices",
  refunds: "resources.refunds",
  inventory: "resources.inventory",
  warranty: "resources.warranty",
  disputes: "resources.disputes",
  audit_logs: "resources.auditLogs",
  roles: "resources.roles",
  system_settings: "resources.systemSettings",
};

const ACTIONS: Array<"read" | "write" | "delete"> = ["read", "write", "delete"];
const ACTION_KEY: Record<"read" | "write" | "delete", string> = {
  read: "actions.read",
  write: "actions.write",
  delete: "actions.delete",
};

interface UpdateResponse {
  data?: {
    role_name: string;
    permissions: string[];
    updated_at: string;
    ws_published: boolean;
    affected_user_count?: number;
  };
}

function flattenPermissions(perms: RolePermission[]): Set<string> {
  const out = new Set<string>();
  for (const p of perms) {
    for (const action of ACTIONS) {
      if (p[action]) out.add(`${p.resource}.${action}`);
    }
  }
  return out;
}

export function RolePermissionsEditor({
  role,
  onClose,
  onSaved,
}: {
  role: Role;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useTranslations("components.admin.rolePermissions");
  const initial = useMemo(() => flattenPermissions(role.permissions), [role]);
  const [desired, setDesired] = useState<Set<string>>(initial);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lockedCodes = useMemo(() => {
    const out = new Set<string>();
    for (const p of role.permissions) {
      if (p.locked) {
        for (const action of ACTIONS) out.add(`${p.resource}.${action}`);
      }
    }
    return out;
  }, [role]);

  function toggle(code: string) {
    if (lockedCodes.has(code)) return;
    setDesired((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  async function handleSubmit() {
    if (reason.trim().length < 4) {
      setError(t("errors.reasonTooShort"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.patch<UpdateResponse>(
        `/api/v1/roles/${role.id}/permissions`,
        {
          permissions: Array.from(desired).sort(),
          reason: reason.trim(),
        },
      );
      onSaved();
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 403) {
          setError(t("errors.forbidden", { code: e.errorCode }));
        } else if (e.status === 422) {
          setError(t("errors.validation", { message: e.message }));
        } else {
          setError(
            t("errors.generic", {
              code: e.errorCode,
              status: e.status,
              message: e.message,
            }),
          );
        }
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="rbac-editor-title"
    >
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
        data-testid="rbac-editor-modal"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <div>
            <h2
              id="rbac-editor-title"
              className="text-lg font-semibold text-[var(--text-primary)]"
            >
              {t("title", { name: role.name })}
            </h2>
            <p className="mt-1 text-[12px] text-[var(--text-secondary)]">
              {t("description", { count: role.user_count })}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            aria-label={t("closeAria")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto px-6 py-4">
          {error && (
            <div
              className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              data-testid="rbac-editor-error"
            >
              {error}
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-[var(--border)]">
            <div className="flex items-center bg-[#F8FAFC] px-4 py-2">
              <div className="w-[200px] text-xs font-semibold text-[var(--text-secondary)]">
                {t("tableHeaderResource")}
              </div>
              {ACTIONS.map((a) => (
                <div
                  key={a}
                  className="flex flex-1 items-center justify-center text-xs font-semibold text-[var(--text-secondary)]"
                >
                  {t(ACTION_KEY[a])}
                </div>
              ))}
            </div>

            {role.permissions.map((row) => (
              <div
                key={row.resource}
                className="flex items-center border-t border-[var(--border)] px-4 py-2"
              >
                <div className="w-[200px] text-[13px] font-medium text-[var(--text-primary)]">
                  {RESOURCE_KEY[row.resource]
                    ? t(RESOURCE_KEY[row.resource])
                    : row.resource}
                </div>
                {ACTIONS.map((action) => {
                  const code = `${row.resource}.${action}`;
                  const checked = desired.has(code);
                  const locked = lockedCodes.has(code);
                  return (
                    <div
                      key={action}
                      className="flex flex-1 items-center justify-center"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={locked}
                        onChange={() => toggle(code)}
                        aria-label={`${row.resource}.${action}`}
                        data-testid={`perm-${code}`}
                        className="h-4 w-4 cursor-pointer rounded border-[var(--border)] disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="mt-4">
            <label className="mb-1 block text-[13px] font-medium text-[var(--text-primary)]">
              {t("reasonLabel")} <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("reasonPlaceholder")}
              rows={2}
              data-testid="rbac-editor-reason"
              className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm focus:border-[var(--primary)] focus:outline-none"
            />
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">
              {t("reasonHint")}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--border)] bg-[#F8FAFC] px-6 py-4">
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed"
          >
            {t("cancel")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="rbac-editor-submit"
            className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-[13px] font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            <span>{t("submit")}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
