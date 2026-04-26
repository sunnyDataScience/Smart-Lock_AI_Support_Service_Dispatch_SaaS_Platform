"use client";

import { useState } from "react";
import { Plus, Pencil, Trash2, Check, Lock } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

interface RoleCard {
  id: string;
  name: string;
  description: string;
  userCount: number;
  isSystem: boolean;
}

const roles: RoleCard[] = [
  {
    id: "admin",
    name: "管理員",
    description: "擁有完整系統管理權限",
    userCount: 3,
    isSystem: true,
  },
  {
    id: "reviewer",
    name: "審核員",
    description: "退款與爭議審核權限",
    userCount: 5,
    isSystem: true,
  },
  {
    id: "technician",
    name: "技師",
    description: "工單執行與庫存查看",
    userCount: 28,
    isSystem: true,
  },
  {
    id: "cs-lead",
    name: "客服主管",
    description: "客服部門主管專用角色",
    userCount: 2,
    isSystem: false,
  },
];

type PermState = "checked" | "unchecked" | "locked";

interface PermissionRow {
  resource: string;
  read: PermState;
  write: PermState;
  delete: PermState;
}

const adminPermissions: PermissionRow[] = [
  { resource: "工單", read: "checked", write: "checked", delete: "checked" },
  { resource: "技師", read: "checked", write: "checked", delete: "checked" },
  { resource: "客戶", read: "checked", write: "checked", delete: "checked" },
  { resource: "結算", read: "checked", write: "checked", delete: "checked" },
  { resource: "發票", read: "checked", write: "checked", delete: "checked" },
  { resource: "退款", read: "checked", write: "checked", delete: "checked" },
  { resource: "庫存", read: "checked", write: "checked", delete: "checked" },
  { resource: "保固", read: "checked", write: "checked", delete: "checked" },
  { resource: "爭議", read: "checked", write: "checked", delete: "checked" },
  { resource: "稽核日誌", read: "checked", write: "checked", delete: "checked" },
  { resource: "角色權限", read: "checked", write: "locked", delete: "locked" },
  { resource: "系統設定", read: "checked", write: "locked", delete: "locked" },
];

function PermCheckbox({ state }: { state: PermState }) {
  if (state === "locked") {
    return (
      <div className="flex items-center justify-center gap-1">
        <div className="flex h-5 w-5 items-center justify-center rounded bg-[#94A3B8]">
          <Check className="h-3 w-3 text-white" />
        </div>
        <Lock className="h-3 w-3 text-[var(--text-disabled)]" />
      </div>
    );
  }

  if (state === "checked") {
    return (
      <div className="flex h-5 w-5 items-center justify-center rounded bg-[var(--primary)]">
        <Check className="h-3 w-3 text-white" />
      </div>
    );
  }

  return (
    <div className="h-5 w-5 rounded border border-[var(--border)] bg-[var(--bg-surface)]" />
  );
}

export default function RolesPage() {
  const [selectedRole, setSelectedRole] = useState("admin");

  const activeRole = roles.find((r) => r.id === selectedRole) ?? roles[0];

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
            <button className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-[10px]">
              <Plus className="h-4 w-4 text-white" />
              <span className="text-sm font-medium text-white">
                建立自訂角色
              </span>
            </button>
          </div>

          {/* Role Cards */}
          <div className="flex gap-4">
            {roles.map((role) => {
              const isSelected = selectedRole === role.id;
              return (
                <button
                  key={role.id}
                  onClick={() => setSelectedRole(role.id)}
                  className={`flex flex-1 flex-col gap-3 rounded-xl p-4 text-left ${
                    isSelected
                      ? "border-2 border-[var(--primary)] bg-[var(--bg-surface)] shadow-[0_2px_8px_rgba(37,99,235,0.13)]"
                      : "border border-[var(--border)] bg-[var(--bg-surface)]"
                  }`}
                >
                  <div className="flex w-full items-center justify-between">
                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {role.name}
                    </span>
                    {role.isSystem ? (
                      <span className="rounded-md bg-[#DBEAFE] px-2 py-[3px] text-[11px] font-semibold text-[var(--primary)]">
                        系統角色
                      </span>
                    ) : (
                      <div className="flex gap-1">
                        <div className="rounded-md p-[6px]">
                          <Pencil className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
                        </div>
                        <div className="rounded-md p-[6px]">
                          <Trash2 className="h-[14px] w-[14px] text-[var(--status-danger)]" />
                        </div>
                      </div>
                    )}
                  </div>
                  <span className="text-[13px] text-[var(--text-secondary)]">
                    {role.description}
                  </span>
                  <span className="w-fit rounded-md bg-[#F1F5F9] px-2 py-1 text-xs font-medium text-[var(--text-secondary)]">
                    使用者 {role.userCount}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Permission Matrix */}
          <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            {/* Matrix Header */}
            <div className="flex items-center justify-between px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="text-base font-semibold text-[var(--text-primary)]">
                  {activeRole.name} 權限矩陣
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button className="rounded-lg px-[14px] py-2">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                    重置為預設
                  </span>
                </button>
                <button className="rounded-lg bg-[var(--primary)] px-[14px] py-2 opacity-50">
                  <span className="text-[13px] font-medium text-white">
                    儲存權限設定
                  </span>
                </button>
              </div>
            </div>

            {/* Matrix Table */}
            <div className="flex-1 overflow-auto">
              {/* Column Headers */}
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

              {/* Permission Rows */}
              {adminPermissions.map((row) => (
                <div
                  key={row.resource}
                  className="flex items-center border-b border-[var(--border)] px-5 py-2"
                >
                  <div className="w-[200px]">
                    <span className="text-[13px] font-medium text-[var(--text-primary)]">
                      {row.resource}
                    </span>
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <PermCheckbox state={row.read} />
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <PermCheckbox state={row.write} />
                  </div>
                  <div className="flex flex-1 items-center justify-center">
                    <PermCheckbox state={row.delete} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
