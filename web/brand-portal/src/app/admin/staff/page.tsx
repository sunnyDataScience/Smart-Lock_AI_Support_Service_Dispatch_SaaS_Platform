"use client";

import { useCallback, useEffect, useState } from "react";
import { UserCog, UserPlus, Check, ClipboardList, ShieldCheck, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface Staff {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

// CR-0143:角色指派 SoD 雙簽(13_Security §3.1)——既有員工角色變更走提案→第二位 admin 核准。
interface RoleAssignment {
  id: string;
  target_user_id: string;
  from_role: string | null;
  to_role: string;
  status: string;
  proposed_by: string | null;
  proposed_at: string | null;
  reason: string | null;
}

// CR-0114 R5:品牌員工自助申請(登入頁 → pending),此頁審核並指派角色。
interface StaffApplication {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  status: string;
  created_at: string | null;
}

// 租戶 Admin 可開通角色（對齊後端 _STAFF_ROLES；13_Security §3.1，SA-06）。
// dispatcher 為保留角色暫不開通（業主裁決 2026-07-07）——不在選項中，
// 但存量帳號仍有效，故 ROLE_LABEL 保留其顯示名。
const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: "operations_manager", label: "營運主管" },
  { value: "customer_service", label: "客服" },
  { value: "reviewer", label: "審核員" },
  { value: "admin", label: "系統管理員" },
];
const ROLE_LABEL: Record<string, string> = {
  ...Object.fromEntries(ROLE_OPTIONS.map((o) => [o.value, o.label])),
  dispatcher: "派工員（保留角色）",
};

export default function StaffPage() {
  const [items, setItems] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("operations_manager");

  // 待審員工申請(CR-0114 R5):列表 + 每列指派角色的暫存選擇
  const [apps, setApps] = useState<StaffApplication[]>([]);
  const [appRole, setAppRole] = useState<Record<string, string>>({});
  const [appBusy, setAppBusy] = useState<string | null>(null);

  // 角色變更 SoD 雙簽(CR-0143)
  const [proposals, setProposals] = useState<RoleAssignment[]>([]);
  const [raTarget, setRaTarget] = useState("");
  const [raRole, setRaRole] = useState("operations_manager");
  const [raReason, setRaReason] = useState("");
  const [raBusy, setRaBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ items: Staff[] }>("/api/v1/staff");
      setItems(res.items ?? []);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadApps = useCallback(async () => {
    try {
      // tenant-scoped v2 端點:GET /tenants/{tid}/staff-applications?status=pending
      const res = await api.get<{ data: StaffApplication[] }>(
        `${tenantPath("/staff-applications")}?status=pending`,
      );
      setApps(res.data ?? []);
    } catch (e) {
      // 待審區為次要面板,失敗不阻斷主頁(員工列表),僅記錯誤 banner
      setError(friendlyError(e));
    }
  }, []);

  const loadProposals = useCallback(async () => {
    try {
      const res = await api.get<{ data: RoleAssignment[] }>(
        `${tenantPath("/role-assignments")}?status=proposed`,
      );
      setProposals(res.data ?? []);
    } catch (e) {
      setError(friendlyError(e));
    }
  }, []);

  useEffect(() => {
    load();
    loadApps();
    loadProposals();
  }, [load, loadApps, loadProposals]);

  async function proposeRoleChange() {
    if (!raTarget) {
      setError("請選擇要變更角色的員工");
      return;
    }
    setRaBusy("propose");
    setError(null);
    setOk(null);
    try {
      await api.post(tenantPath("/role-assignments"), {
        target_user_id: raTarget,
        to_role: raRole,
        reason: raReason.trim() || null,
      });
      setOk("角色變更提案已建立,待另一位管理員核准(SoD 雙簽)");
      setRaTarget("");
      setRaReason("");
      await loadProposals();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setRaBusy(null);
    }
  }

  async function decideProposal(p: RoleAssignment, action: "approve" | "reject") {
    setRaBusy(p.id);
    setError(null);
    setOk(null);
    try {
      await api.post(tenantPath(`/role-assignments/${p.id}:${action}`), {});
      setOk(action === "approve" ? "已核准並套用角色變更" : "已拒絕提案");
      await Promise.all([loadProposals(), load()]);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setRaBusy(null);
    }
  }

  async function approveApp(app: StaffApplication) {
    const assigned = appRole[app.id] ?? "operations_manager";
    setAppBusy(app.id);
    setError(null);
    setOk(null);
    try {
      await api.post(tenantPath(`/staff-applications/${app.id}:approve`), {
        role: assigned,
      });
      setOk(`已核准 ${app.name}(${app.email})並指派為「${ROLE_LABEL[assigned] ?? assigned}」`);
      await Promise.all([loadApps(), load()]);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setAppBusy(null);
    }
  }

  async function rejectApp(app: StaffApplication) {
    const reason = window.prompt(`拒絕「${app.name}」的申請,請填寫原因(至少 3 個字):`);
    if (reason == null) return; // 取消
    if (reason.trim().length < 3) {
      setError("拒絕原因至少 3 個字");
      return;
    }
    setAppBusy(app.id);
    setError(null);
    setOk(null);
    try {
      await api.post(tenantPath(`/staff-applications/${app.id}:reject`), {
        reason: reason.trim(),
      });
      setOk(`已拒絕 ${app.name}(${app.email})的申請`);
      await loadApps();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setAppBusy(null);
    }
  }

  async function create() {
    if (!name.trim() || !email.trim() || password.length < 8) {
      setError("請填寫姓名、Email，密碼至少 8 碼");
      return;
    }
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      await api.post("/api/v1/staff", {
        name: name.trim(),
        email: email.trim(),
        password,
        role,
        phone: phone.trim() || null,
      });
      setOk(`已建立 ${ROLE_LABEL[role] ?? role}：${email.trim()}`);
      setName("");
      setEmail("");
      setPassword("");
      setPhone("");
      await load();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <UserCog className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">員工帳號管理</h1>
          <span className="text-[13px] text-[var(--text-secondary)]">共 {items.length} 位</span>
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
          {ok && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
              <Check className="h-4 w-4" /> {ok}
            </div>
          )}

          {/* 待審員工申請(CR-0114 R5:登入頁自助申請 → 此處審核並指派角色) */}
          {apps.length > 0 && (
            <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4">
              <div className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-amber-800">
                <ClipboardList className="h-5 w-5" /> 待審員工申請
                <span className="rounded-full bg-amber-200 px-2 py-[1px] text-[12px] text-amber-900">
                  {apps.length}
                </span>
              </div>
              <div className="flex flex-col gap-2">
                {apps.map((app) => (
                  <div
                    key={app.id}
                    className="flex flex-col gap-3 rounded-md border border-amber-200 bg-[var(--bg-surface)] p-3 md:flex-row md:items-center md:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="font-medium text-[var(--text-primary)]">{app.name}</div>
                      <div className="text-[13px] text-[var(--text-secondary)]">
                        {app.email}
                        {app.phone ? ` · ${app.phone}` : ""}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <select
                        value={appRole[app.id] ?? "operations_manager"}
                        onChange={(e) =>
                          setAppRole((m) => ({ ...m, [app.id]: e.target.value }))
                        }
                        disabled={appBusy === app.id}
                        className="rounded-md border border-[var(--border)] px-2 py-[6px] text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-50"
                        aria-label={`為 ${app.name} 指派角色`}
                      >
                        {ROLE_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => approveApp(app)}
                        disabled={appBusy === app.id}
                        className="inline-flex h-[34px] items-center gap-1 rounded-md bg-[var(--primary)] px-3 text-[13px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
                      >
                        <Check className="h-4 w-4" /> 核准並指派
                      </button>
                      <button
                        onClick={() => rejectApp(app)}
                        disabled={appBusy === app.id}
                        className="inline-flex h-[34px] items-center gap-1 rounded-md border border-red-300 px-3 text-[13px] font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                      >
                        <X className="h-4 w-4" /> 拒絕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 建立員工 */}
          <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
            <div className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-[var(--text-primary)]">
              <UserPlus className="h-5 w-5 text-[var(--primary)]" /> 建立員工帳號
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              <Field label="姓名" required>
                <input value={name} onChange={(e) => setName(e.target.value)} className={INPUT} />
              </Field>
              <Field label="Email" required>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={INPUT} />
              </Field>
              <Field label="密碼（≥8 碼）" required>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={INPUT} />
              </Field>
              <Field label="電話">
                <input value={phone} onChange={(e) => setPhone(e.target.value)} className={INPUT} />
              </Field>
              <Field label="角色" required>
                <select value={role} onChange={(e) => setRole(e.target.value)} className={INPUT}>
                  {ROLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="flex items-end">
                <button
                  onClick={create}
                  disabled={busy}
                  className="h-[38px] w-full rounded-md bg-[var(--primary)] px-4 text-sm font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
                >
                  {busy ? "建立中…" : "建立帳號"}
                </button>
              </div>
            </div>
          </div>

          {/* 角色變更 SoD 雙簽(CR-0143;13_Security §3.1) */}
          <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
            <div className="mb-1 flex items-center gap-2 text-[15px] font-semibold text-[var(--text-primary)]">
              <ShieldCheck className="h-5 w-5 text-[var(--primary)]" /> 角色變更(SoD 雙簽)
            </div>
            <p className="mb-3 text-[12px] text-[var(--text-secondary)]">
              既有員工的角色變更須由一位管理員提案、另一位管理員核准(同一人核准自己的提案會被拒絕)。
            </p>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
              <Field label="員工" required>
                <select value={raTarget} onChange={(e) => setRaTarget(e.target.value)} className={INPUT}>
                  <option value="">— 選擇員工 —</option>
                  {items.filter((s) => s.role !== "technician").map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}({ROLE_LABEL[s.role] ?? s.role})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="變更為" required>
                <select value={raRole} onChange={(e) => setRaRole(e.target.value)} className={INPUT}>
                  {ROLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="原因">
                <input value={raReason} onChange={(e) => setRaReason(e.target.value)}
                       placeholder="如:職務調整" className={INPUT} />
              </Field>
              <div className="flex items-end">
                <button
                  onClick={proposeRoleChange}
                  disabled={raBusy === "propose"}
                  className="h-[38px] w-full rounded-md bg-[var(--primary)] px-4 text-sm font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
                >
                  {raBusy === "propose" ? "提案中…" : "建立提案"}
                </button>
              </div>
            </div>
            {proposals.length > 0 && (
              <div className="mt-4 overflow-hidden rounded-md border border-[var(--border)]">
                <table className="w-full text-[13px]">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-3 py-2 text-left">員工</th>
                      <th className="px-3 py-2 text-left">變更</th>
                      <th className="px-3 py-2 text-left">原因</th>
                      <th className="px-3 py-2 text-right">待第二位管理員核准</th>
                    </tr>
                  </thead>
                  <tbody>
                    {proposals.map((p) => {
                      const staff = items.find((s) => s.id === p.target_user_id);
                      return (
                        <tr key={p.id} className="border-t border-[var(--border)]">
                          <td className="px-3 py-2 font-medium">{staff?.name ?? p.target_user_id.slice(0, 8)}</td>
                          <td className="px-3 py-2">
                            {(ROLE_LABEL[p.from_role ?? ""] ?? p.from_role ?? "—")} → <strong>{ROLE_LABEL[p.to_role] ?? p.to_role}</strong>
                          </td>
                          <td className="px-3 py-2 text-[var(--text-secondary)]">{p.reason ?? "—"}</td>
                          <td className="px-3 py-2 text-right">
                            <button
                              onClick={() => decideProposal(p, "approve")}
                              disabled={raBusy === p.id}
                              className="mr-2 rounded-md bg-[#15803D] px-3 py-[6px] text-[12px] font-semibold text-white disabled:opacity-50"
                            >
                              核准並套用
                            </button>
                            <button
                              onClick={() => decideProposal(p, "reject")}
                              disabled={raBusy === p.id}
                              className="rounded-md border border-[var(--border)] px-3 py-[6px] text-[12px] font-semibold text-[var(--text-primary)] disabled:opacity-50"
                            >
                              拒絕
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* 員工列表 */}
          {loading ? (
            <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-[var(--text-disabled)]">目前沒有員工帳號</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <table className="w-full text-sm">
                <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-4 py-3 text-left">姓名</th>
                    <th className="px-4 py-3 text-left">Email</th>
                    <th className="px-4 py-3 text-left">角色</th>
                    <th className="px-4 py-3 text-left">狀態</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id} className="border-t border-[var(--border)]">
                      <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{s.name}</td>
                      <td className="px-4 py-3 text-[var(--text-secondary)]">{s.email}</td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-[#E0E7FF] px-2 py-[2px] text-[12px] text-[#4338CA]">
                          {ROLE_LABEL[s.role] ?? s.role}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {s.is_active ? (
                          <span className="text-[12px] text-[#15803D]">啟用</span>
                        ) : (
                          <span className="text-[12px] text-[var(--text-disabled)]">停用</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const INPUT =
  "w-full rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      {children}
    </label>
  );
}
