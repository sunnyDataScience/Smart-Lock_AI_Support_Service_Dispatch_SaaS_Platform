"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Trash2, X } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { cacheInvalidate } from "@/lib/cache";

/* CR-0104：技能認證矩陣（真資料）。取代原本前端寫死的 5 列 mock，
   改讀 GET /tenants/{tid}/technicians/{id}/certifications，並提供 admin 後台維護（新增/編輯/刪除）。
   狀態（有效/即將到期/已過期）由後端依到期日 computed。 */

interface Certification {
  id: string;
  technician_id: string;
  cert_name: string;
  brand: string | null;
  obtained_at: string | null;
  expires_at: string | null;
  status: "valid" | "expiring_soon" | "expired";
  is_mock: boolean;
  created_at: string | null;
}

const STATUS_STYLE: Record<
  Certification["status"],
  { label: string; textColor: string; bgColor: string }
> = {
  valid: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" },
  expiring_soon: { label: "即將到期", textColor: "#92400E", bgColor: "#FEF3C7" },
  expired: { label: "已過期", textColor: "#991B1B", bgColor: "#FEE2E2" },
};

interface CertForm {
  cert_name: string;
  brand: string;
  obtained_at: string;
  expires_at: string;
}

const EMPTY_FORM: CertForm = { cert_name: "", brand: "", obtained_at: "", expires_at: "" };

function fmtDate(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "—";
}

interface Props {
  tenantId: string;
  technicianId: string;
}

export default function CertificationMatrix({ tenantId, technicianId }: Props) {
  const [certs, setCerts] = useState<Certification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editId, setEditId] = useState<string | null>(null); // null = 未開；"new" = 新增；其他 = 編輯該 id
  const [form, setForm] = useState<CertForm>(EMPTY_FORM);
  const [formMsg, setFormMsg] = useState<string | null>(null);

  const basePath = `/tenants/${encodeURIComponent(tenantId)}/technicians/${encodeURIComponent(technicianId)}/certifications`;

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.get<{ data: Certification[] }>(basePath);
      setCerts(res.data ?? []);
    } catch (e) {
      setError(
        e instanceof ApiError ? `${e.errorCode} (${e.status})：${e.message}` : String(e),
      );
    }
  }, [basePath]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      await load();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  function openNew() {
    setForm(EMPTY_FORM);
    setFormMsg(null);
    setEditId("new");
  }

  function openEdit(c: Certification) {
    setForm({
      cert_name: c.cert_name,
      brand: c.brand ?? "",
      obtained_at: c.obtained_at ?? "",
      expires_at: c.expires_at ?? "",
    });
    setFormMsg(null);
    setEditId(c.id);
  }

  async function handleSave() {
    if (!form.cert_name.trim()) {
      setFormMsg("認證項目為必填");
      return;
    }
    setBusy(true);
    setFormMsg(null);
    const payload = {
      cert_name: form.cert_name.trim(),
      brand: form.brand.trim() || null,
      obtained_at: form.obtained_at || null,
      expires_at: form.expires_at || null,
    };
    try {
      if (editId === "new") {
        await api.post(basePath, payload);
      } else {
        await api.patch(`${basePath}/${encodeURIComponent(editId!)}`, payload);
      }
      cacheInvalidate("GET:");
      setEditId(null);
      await load();
    } catch (e) {
      setFormMsg(
        e instanceof ApiError ? `儲存失敗：${e.errorCode} (${e.status})` : "儲存失敗",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(c: Certification) {
    if (!window.confirm(`確定刪除認證「${c.cert_name}」？`)) return;
    setBusy(true);
    try {
      await api.delete(`${basePath}/${encodeURIComponent(c.id)}`);
      cacheInvalidate("GET:");
      await load();
    } catch (e) {
      setError(
        e instanceof ApiError ? `刪除失敗：${e.errorCode} (${e.status})` : "刪除失敗",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">技能認證矩陣</h2>
        <button
          onClick={openNew}
          disabled={busy}
          className="flex items-center gap-[6px] rounded-lg border border-[var(--primary)] px-3 py-1.5 text-[13px] text-[var(--primary)] hover:bg-[var(--primary-light)] disabled:opacity-50"
        >
          <Plus className="h-[14px] w-[14px]" />
          新增認證
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        <div className="flex h-[40px] items-center bg-[var(--bg-page)] px-4">
          <div className="flex w-[180px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">認證項目</span></div>
          <div className="flex w-[110px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">品牌</span></div>
          <div className="flex w-[110px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">取得日期</span></div>
          <div className="flex w-[110px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">到期日期</span></div>
          <div className="flex w-[90px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">狀態</span></div>
          <div className="flex flex-1 justify-end"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">操作</span></div>
        </div>

        {loading ? (
          <div className="flex h-[60px] items-center justify-center text-[13px] text-[var(--text-disabled)]">載入中…</div>
        ) : certs.length === 0 ? (
          <div className="flex h-[60px] items-center justify-center text-[13px] text-[var(--text-disabled)]">
            尚無認證資料，點「新增認證」登錄。
          </div>
        ) : (
          certs.map((c, idx) => {
            const st = STATUS_STYLE[c.status] ?? STATUS_STYLE.valid;
            return (
              <div
                key={c.id}
                className={`flex h-[44px] items-center px-4 ${idx < certs.length - 1 ? "border-b border-[var(--border)]" : ""}`}
              >
                <div className="flex w-[180px]"><span className="text-[13px] text-[var(--text-primary)]">{c.cert_name}</span></div>
                <div className="flex w-[110px]"><span className="text-[13px] text-[var(--text-primary)]">{c.brand || "—"}</span></div>
                <div className="flex w-[110px]"><span className="text-[13px] text-[var(--text-primary)]">{fmtDate(c.obtained_at)}</span></div>
                <div className="flex w-[110px]"><span className="text-[13px] text-[var(--text-primary)]">{fmtDate(c.expires_at)}</span></div>
                <div className="flex w-[90px]">
                  <span
                    className="rounded-full px-[10px] py-[2px] text-[11px] font-medium"
                    style={{ color: st.textColor, backgroundColor: st.bgColor }}
                  >
                    {st.label}
                  </span>
                </div>
                <div className="flex flex-1 items-center justify-end gap-2">
                  <button onClick={() => openEdit(c)} disabled={busy} aria-label="編輯" className="text-[var(--text-secondary)] hover:text-[var(--primary)] disabled:opacity-50">
                    <Pencil className="h-[14px] w-[14px]" />
                  </button>
                  <button onClick={() => handleDelete(c)} disabled={busy} aria-label="刪除" className="text-[var(--text-secondary)] hover:text-[var(--error)] disabled:opacity-50">
                    <Trash2 className="h-[14px] w-[14px]" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 新增 / 編輯 認證 modal */}
      {editId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-[var(--bg-surface)] p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[16px] font-semibold text-[var(--text-primary)]">
                {editId === "new" ? "新增認證" : "編輯認證"}
              </h3>
              <button onClick={() => setEditId(null)} aria-label="關閉" className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">認證項目 *</span>
                <input
                  value={form.cert_name}
                  onChange={(e) => setForm((f) => ({ ...f, cert_name: e.target.value }))}
                  placeholder="電子鎖安裝認證"
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">品牌</span>
                <input
                  value={form.brand}
                  onChange={(e) => setForm((f) => ({ ...f, brand: e.target.value }))}
                  placeholder="Yale"
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
              <div className="flex gap-3">
                <label className="flex flex-1 flex-col gap-1 text-sm">
                  <span className="text-[var(--text-secondary)]">取得日期</span>
                  <input
                    type="date"
                    value={form.obtained_at}
                    onChange={(e) => setForm((f) => ({ ...f, obtained_at: e.target.value }))}
                    className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                  />
                </label>
                <label className="flex flex-1 flex-col gap-1 text-sm">
                  <span className="text-[var(--text-secondary)]">到期日期</span>
                  <input
                    type="date"
                    value={form.expires_at}
                    onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value }))}
                    className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                  />
                </label>
              </div>
            </div>
            {formMsg && <p className="mt-3 text-[13px] text-red-600">{formMsg}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setEditId(null)} disabled={busy} className="rounded border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50">
                取消
              </button>
              <button onClick={handleSave} disabled={busy} className="rounded bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
                {busy ? "儲存中…" : "儲存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
