"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Check, Lock, RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Role = components["schemas"]["Role"];
type RolePermission = components["schemas"]["RolePermission"];
type RoleResource = components["schemas"]["RoleResource"];

interface RolesResponse {
  data?: Role[];
  message?: string;
}

const RESOURCE_LABELS: Record<RoleResource, string> = {
  work_orders: "工單",
  technicians: "技師",
  customers: "客戶",
  accounting: "結算",
  invoices: "發票",
  refunds: "退款",
  inventory: "庫存",
  warranty: "保固",
  disputes: "爭議",
  audit_logs: "稽核日誌",
  roles: "角色權限",
  system_settings: "系統設定",
};

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
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function fetchRoles() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<RolesResponse>("/api/v1/roles");
      const items = res.data ?? [];
      setRoles(items);
      if (items.length > 0 && selectedId === null) {
        setSelectedId(items[0].id);
      }
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchRoles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeRole = useMemo(
    () =>
      roles.find((r) => r.id === selectedId) ??
      (roles.length > 0 ? roles[0] : null),
    [roles, selectedId],
  );

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
              角色與權限管理
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchRoles}
                disabled={loading}
                title="重新整理"
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${
                    loading ? "animate-spin" : ""
                  }`}
                />
              </button>
              <button
                disabled
                title="即將推出（需自訂角色 CRUD endpoint）"
                className="flex cursor-not-allowed items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-[10px] opacity-50"
              >
                <Plus className="h-4 w-4 text-white" />
                <span className="text-sm font-medium text-white">
                  建立自訂角色
                </span>
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] leading-relaxed text-amber-800">
            目前僅展示 5 個系統角色與其權限矩陣（鏡射後端 role_required 守衛邏輯）；
            自訂角色 CRUD 與權限矩陣編輯需要 roles / role_permissions 表，待 RBAC 模組接入後再上線。
          </div>

          {/* Role Cards */}
          {loading && roles.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              載入中…
            </div>
          ) : roles.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              尚無角色資料
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
                          系統
                        </span>
                      )}
                    </div>
                    <span className="line-clamp-2 text-[12px] leading-snug text-[var(--text-secondary)]">
                      {role.description}
                    </span>
                    <span className="w-fit rounded-md bg-[#F1F5F9] px-2 py-1 text-xs font-medium text-[var(--text-secondary)]">
                      使用者 {role.user_count}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Permission Matrix */}
          {activeRole && (
            <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <span className="text-base font-semibold text-[var(--text-primary)]">
                    {activeRole.name} 權限矩陣
                  </span>
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    （read-only；鎖定圖示代表系統強制）
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    disabled
                    title="即將推出"
                    className="cursor-not-allowed rounded-lg px-[14px] py-2 opacity-50"
                  >
                    <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                      重置為預設
                    </span>
                  </button>
                  <button
                    disabled
                    title="即將推出（需 role_permissions 表）"
                    className="cursor-not-allowed rounded-lg bg-[var(--primary)] px-[14px] py-2 opacity-50"
                  >
                    <span className="text-[13px] font-medium text-white">
                      儲存權限設定
                    </span>
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-auto">
                <div className="flex items-center border-b border-[var(--border)] bg-[#F8FAFC] px-5 py-[10px]">
                  <div className="w-[200px]">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      資源
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      讀取
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      寫入
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      刪除
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
                        {RESOURCE_LABELS[row.resource] ?? row.resource}
                      </span>
                    </div>
                    <div className="flex flex-1 items-center justify-center">
                      <PermCell granted={row.read} locked={!!row.locked} />
                    </div>
                    <div className="flex flex-1 items-center justify-center">
                      <PermCell granted={row.write} locked={!!row.locked} />
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
    </div>
  );
}
