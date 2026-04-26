"use client";

import { ShieldCheck } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

export default function RolesPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          <div className="flex flex-col gap-2">
            <span className="text-[13px] text-[var(--text-secondary)]">
              首頁 &gt; 稽核與權限 &gt; RBAC 管理
            </span>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              RBAC 管理
            </h1>
          </div>

          <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            <ShieldCheck className="h-16 w-16 text-[var(--text-disabled)]" />
            <span className="text-base font-medium text-[var(--text-secondary)]">
              RBAC 角色權限管理開發中
            </span>
            <span className="text-sm text-[var(--text-disabled)]">
              此頁面即將上線，敬請期待
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
