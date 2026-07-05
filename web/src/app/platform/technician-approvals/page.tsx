"use client";

// CR-0114 R3 平台 console — 師傅審核。
// 跨品牌師傅清單(直查共用師傅庫 authority);核准/拒絕/停權/復權/終止。
// initiator 取已驗簽 token(後端 require_platform_admin),不需前端自報。

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

type TechStatus =
  | "pending_approval"
  | "active"
  | "suspended"
  | "rejected"
  | "terminated"
  | "inactive";

interface PlatformTechnician {
  id: string;
  tenant_id: string | null;
  name: string;
  phone: string;
  email: string;
  status: TechStatus;
  capabilities: string[];
  service_regions: string[];
  created_at: string | null;
  is_active: boolean;
}

const STATUS_LABEL: Record<TechStatus, string> = {
  pending_approval: "待審核",
  active: "啟用中",
  suspended: "已停權",
  rejected: "已拒絕",
  terminated: "已終止",
  inactive: "未啟用",
};

const STATUS_CLS: Record<TechStatus, string> = {
  pending_approval: "bg-amber-50 text-amber-700 border-amber-200",
  active: "bg-green-50 text-green-700 border-green-200",
  suspended: "bg-red-50 text-red-700 border-red-200",
  rejected: "bg-gray-100 text-gray-600 border-gray-200",
  terminated: "bg-gray-100 text-gray-600 border-gray-200",
  inactive: "bg-gray-100 text-gray-600 border-gray-200",
};

// 每個狀態可執行的生命週期動作(對齊後端狀態機 _ALLOWED_TRANSITIONS)
type Action = "onboard-approve" | "onboard-reject" | "suspend" | "reactivate" | "terminate";
const ACTIONS: Record<TechStatus, { action: Action; label: string; danger?: boolean }[]> = {
  pending_approval: [
    { action: "onboard-approve", label: "核准" },
    { action: "onboard-reject", label: "拒絕", danger: true },
  ],
  active: [
    { action: "suspend", label: "停權", danger: true },
    { action: "terminate", label: "終止", danger: true },
  ],
  suspended: [
    { action: "reactivate", label: "復權" },
    { action: "terminate", label: "終止", danger: true },
  ],
  rejected: [{ action: "terminate", label: "終止", danger: true }],
  inactive: [
    { action: "reactivate", label: "啟用" },
    { action: "terminate", label: "終止", danger: true },
  ],
  terminated: [],
};

const FILTERS: { value: string; label: string }[] = [
  { value: "pending_approval", label: "待審核" },
  { value: "active", label: "啟用中" },
  { value: "suspended", label: "已停權" },
  { value: "", label: "全部" },
];

export default function TechnicianApprovalsPage() {
  const [filter, setFilter] = useState<string>("pending_approval");
  const [rows, setRows] = useState<PlatformTechnician[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = filter ? `?status=${filter}` : "";
      const res = await api.get<{ data: PlatformTechnician[] }>(
        `/api/v1/platform/technicians${qs}`,
      );
      setRows(res.data);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function runAction(tech: PlatformTechnician, action: Action, label: string) {
    let body: Record<string, string> = {};
    // approve 外的動作皆需 reason（後端 _change_status_and_audit 要求 ≥3 字）
    if (action !== "onboard-approve") {
      const reason = window.prompt(`「${tech.name}」${label}原因（至少 3 字，記入稽核）：`, "");
      if (reason === null) return;
      if (reason.trim().length < 3) {
        window.alert("原因至少需 3 個字");
        return;
      }
      body = { reason: reason.trim() };
    }
    setBusyId(tech.id);
    try {
      await api.post(`/api/v1/platform/technicians/${tech.id}:${action}`, body);
      await load();
    } catch (err) {
      window.alert(friendlyError(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">師傅審核</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          鎖匠師傅的註冊審核與生命週期管理。師傅平台全品牌共用，審核由平台方統一負責。
        </p>
      </div>

      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            type="button"
            onClick={() => setFilter(f.value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === f.value
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          目前沒有符合條件的師傅
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((tech) => (
            <div
              key={tech.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {tech.name || "（未命名）"}
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[tech.status]}`}>
                      {STATUS_LABEL[tech.status]}
                    </span>
                    {!tech.is_active && tech.status === "active" && (
                      <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                        登入未同步
                      </span>
                    )}
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    <span>電話：{tech.phone || "—"}</span>
                    <span>Email：{tech.email || "—"}</span>
                    {tech.capabilities.length > 0 && (
                      <span className="sm:col-span-2">技能：{tech.capabilities.join("、")}</span>
                    )}
                    {tech.service_regions.length > 0 && (
                      <span className="sm:col-span-2">服務區域：{tech.service_regions.join("、")}</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  {ACTIONS[tech.status].map((a) => (
                    <button
                      key={a.action}
                      type="button"
                      disabled={busyId === tech.id}
                      onClick={() => runAction(tech, a.action, a.label)}
                      className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition disabled:opacity-50 ${
                        a.danger
                          ? "border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
                          : "bg-[var(--primary)] text-white hover:opacity-90"
                      }`}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
