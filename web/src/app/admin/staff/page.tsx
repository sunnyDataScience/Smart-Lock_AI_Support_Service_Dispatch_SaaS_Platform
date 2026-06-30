"use client";

import { useCallback, useEffect, useState } from "react";
import { UserCog, UserPlus, Check } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api } from "@/lib/api";
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

// CR-0094：可建立的後台角色（對齊後端 _STAFF_ROLES / auth._ADMIN_WEB_ROLES）
const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: "operations_manager", label: "營運主管" },
  { value: "dispatcher", label: "派工員" },
  { value: "customer_service", label: "客服" },
  { value: "reviewer", label: "審核員" },
  { value: "admin", label: "系統管理員" },
];
const ROLE_LABEL: Record<string, string> = Object.fromEntries(
  ROLE_OPTIONS.map((o) => [o.value, o.label]),
);

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

  useEffect(() => {
    load();
  }, [load]);

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
