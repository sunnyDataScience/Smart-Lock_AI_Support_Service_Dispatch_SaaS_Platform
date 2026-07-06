"use client";

// CR-0114 §8 追補收尾 — 平台 console 師傅詳情（身分域管理）。
// 個人資料 + 編輯（含等級）+ 認證 CRUD + 生命週期歷史 + 生命週期動作。
// 排班/獎懲屬品牌營運（per-brand 工單/財務），不在跨品牌平台視角 —— 故不含。
// 內部工具 → 文案直接繁中。

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface Technician {
  id: string;
  name: string;
  phone: string;
  level: string;
  availability: string;
  skills: string[];
  service_areas: string[];
  rating: number;
  completed_orders_count: number | null;
  status: string | null;
  created_at: string;
  authorized_brands?: string[];
}

interface Certification {
  id: string;
  cert_name: string;
  brand: string | null;
  obtained_at: string | null;
  expires_at: string | null;
  status: "valid" | "expiring_soon" | "expired";
}

interface LifecycleEvent {
  id: string;
  event_type: string;
  previous_status: string | null;
  new_status: string | null;
  reason: string | null;
  actor_role: string | null;
  created_at: string | null;
}

const STATUS_LABEL: Record<string, string> = {
  pending_approval: "待審核",
  active: "啟用中",
  suspended: "已停權",
  rejected: "已拒絕",
  terminated: "已終止",
  inactive: "未啟用",
};

const CERT_STATUS: Record<Certification["status"], { label: string; cls: string }> = {
  valid: { label: "有效", cls: "bg-green-50 text-green-700 border-green-200" },
  expiring_soon: { label: "即將到期", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  expired: { label: "已過期", cls: "bg-red-50 text-red-700 border-red-200" },
};

const LEVELS = ["S", "A", "B", "C"];

function fmtDate(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "—";
}

export default function PlatformTechnicianDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [tech, setTech] = useState<Technician | null>(null);
  const [certs, setCerts] = useState<Certification[]>([]);
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [certEdit, setCertEdit] = useState<Certification | "new" | null>(null);

  const base = `/api/v1/platform/technicians/${encodeURIComponent(id)}`;

  const load = useCallback(async () => {
    setError(null);
    try {
      const [t, c, e] = await Promise.all([
        api.get<{ data: Technician }>(base),
        api.get<{ data: Certification[] }>(`${base}/certifications`),
        api.get<{ data: LifecycleEvent[] }>(
          `/api/v1/platform/technicians/lifecycle-events?tech_id=${encodeURIComponent(id)}`,
        ),
      ]);
      setTech(t.data);
      setCerts(c.data ?? []);
      setEvents(e.data ?? []);
    } catch (err) {
      setError(friendlyError(err));
    }
  }, [base, id]);

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

  async function deleteCert(cert: Certification) {
    if (!window.confirm(`確定刪除認證「${cert.cert_name}」？`)) return;
    try {
      await api.delete(`${base}/certifications/${encodeURIComponent(cert.id)}`);
      await load();
    } catch (e) {
      window.alert(friendlyError(e));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/platform/technicians"
        className="flex w-fit items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden />
        返回師傅管理
      </Link>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && !tech ? (
        <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
      ) : !tech ? (
        <p className="text-sm text-[var(--text-secondary)]">找不到此師傅</p>
      ) : (
        <>
          {/* 個人資料 */}
          <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-[var(--text-primary)]">{tech.name}</h1>
                <span className="rounded-md border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                  {STATUS_LABEL[tech.status ?? ""] ?? tech.status}
                </span>
                <span className="rounded-md bg-[var(--bg-page)] px-2 py-0.5 text-xs font-semibold text-[var(--text-secondary)]">
                  等級 {tech.level}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setEditOpen(true)}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-primary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
              >
                <Pencil className="h-3.5 w-3.5" aria-hidden />
                編輯
              </button>
            </div>
            <div className="mt-4 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
              <Info label="電話" value={tech.phone || "—"} />
              <Info label="評分" value={tech.rating.toFixed(1)} />
              <Info label="完成工單" value={String(tech.completed_orders_count ?? 0)} />
              <Info label="建立時間" value={fmtDate(tech.created_at)} />
              <Info label="專長品牌" value={tech.skills.length ? tech.skills.join("、") : "—"} span />
              <Info label="服務區域" value={tech.service_areas.length ? tech.service_areas.join("、") : "—"} span />
              {tech.authorized_brands && tech.authorized_brands.length > 0 && (
                <Info label="已授權品牌" value={tech.authorized_brands.join("、")} span />
              )}
            </div>
          </section>

          {/* 技能認證矩陣 */}
          <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-[var(--text-primary)]">技能認證矩陣</h2>
              <button
                type="button"
                onClick={() => setCertEdit("new")}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary)] transition hover:bg-[var(--primary-subtle,rgba(59,130,246,0.08))]"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden />
                新增認證
              </button>
            </div>
            {certs.length === 0 ? (
              <p className="py-6 text-center text-sm text-[var(--text-secondary)]">尚無認證資料</p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--border)]">
                {certs.map((c) => (
                  <div key={c.id} className="flex items-center gap-4 py-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[var(--text-primary)]">{c.cert_name}</span>
                        <span className={`rounded-md border px-2 py-0.5 text-xs ${CERT_STATUS[c.status].cls}`}>
                          {CERT_STATUS[c.status].label}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-[var(--text-secondary)]">
                        {c.brand ? `品牌：${c.brand}　` : ""}取得：{fmtDate(c.obtained_at)}　到期：{fmtDate(c.expires_at)}
                      </div>
                    </div>
                    <button type="button" onClick={() => setCertEdit(c)} aria-label="編輯認證" className="text-[var(--text-secondary)] hover:text-[var(--primary)]">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button type="button" onClick={() => deleteCert(c)} aria-label="刪除認證" className="text-[var(--text-secondary)] hover:text-red-600">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 生命週期歷史 */}
          <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <h2 className="mb-4 text-base font-semibold text-[var(--text-primary)]">生命週期歷史</h2>
            {events.length === 0 ? (
              <p className="py-6 text-center text-sm text-[var(--text-secondary)]">尚無事件</p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--border)]">
                {events.map((ev) => (
                  <div key={ev.id} className="flex items-start justify-between gap-4 py-3 text-sm">
                    <div>
                      <span className="font-medium text-[var(--text-primary)]">
                        {STATUS_LABEL[ev.previous_status ?? ""] ?? ev.previous_status ?? "—"} → {STATUS_LABEL[ev.new_status ?? ""] ?? ev.new_status}
                      </span>
                      {ev.reason && <span className="text-[var(--text-secondary)]">　原因：{ev.reason}</span>}
                    </div>
                    <span className="whitespace-nowrap text-xs text-[var(--text-secondary)]">
                      {ev.created_at ? ev.created_at.slice(0, 16).replace("T", " ") : "—"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {editOpen && tech && (
        <EditTechnicianModal
          tech={tech}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            setEditOpen(false);
            load();
          }}
        />
      )}

      {certEdit !== null && (
        <CertModal
          basePath={base}
          cert={certEdit === "new" ? null : certEdit}
          onClose={() => setCertEdit(null)}
          onSaved={() => {
            setCertEdit(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function Info({ label, value, span }: { label: string; value: string; span?: boolean }) {
  return (
    <div className={span ? "sm:col-span-2" : ""}>
      <span className="text-[var(--text-secondary)]">{label}：</span>
      <span className="text-[var(--text-primary)]">{value}</span>
    </div>
  );
}

function EditTechnicianModal({
  tech,
  onClose,
  onSaved,
}: {
  tech: Technician;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    name: tech.name,
    phone: tech.phone,
    skills: tech.skills.join(", "),
    regions: tech.service_areas.join(", "),
    level: tech.level,
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const splitCsv = (s: string) =>
    s.split(/[,，、]/).map((x) => x.trim()).filter(Boolean);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      await api.patch(`/api/v1/platform/technicians/${encodeURIComponent(tech.id)}`, {
        display_name: form.name.trim() || undefined,
        phone: form.phone.trim() || undefined,
        capabilities: splitCsv(form.skills),
        coverage_areas: splitCsv(form.regions),
        level: form.level || undefined,
      });
      onSaved();
    } catch (e) {
      setMsg(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ModalShell title="編輯師傅資料" onClose={onClose}>
      <div className="flex flex-col gap-3">
        <ModalField label="姓名" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} />
        <ModalField label="聯絡電話" value={form.phone} onChange={(v) => setForm((f) => ({ ...f, phone: v }))} />
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-[var(--text-secondary)]">等級</span>
          <select
            value={form.level}
            onChange={(e) => setForm((f) => ({ ...f, level: e.target.value }))}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none"
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </label>
        <ModalField label="專長品牌（逗號分隔）" value={form.skills} onChange={(v) => setForm((f) => ({ ...f, skills: v }))} placeholder="Yale, Dormakaba" />
        <ModalField label="服務區域（逗號分隔）" value={form.regions} onChange={(v) => setForm((f) => ({ ...f, regions: v }))} placeholder="台北市, 新北市" />
      </div>
      {msg && <p className="mt-3 text-[13px] text-red-600">{msg}</p>}
      <ModalActions busy={busy} onClose={onClose} onSave={save} saveLabel="儲存" />
    </ModalShell>
  );
}

function CertModal({
  basePath,
  cert,
  onClose,
  onSaved,
}: {
  basePath: string;
  cert: Certification | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    cert_name: cert?.cert_name ?? "",
    brand: cert?.brand ?? "",
    obtained_at: cert?.obtained_at ?? "",
    expires_at: cert?.expires_at ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function save() {
    if (!form.cert_name.trim()) {
      setMsg("認證項目為必填");
      return;
    }
    setBusy(true);
    setMsg(null);
    const payload = {
      cert_name: form.cert_name.trim(),
      brand: form.brand.trim() || null,
      obtained_at: form.obtained_at || null,
      expires_at: form.expires_at || null,
    };
    try {
      if (cert) {
        await api.patch(`${basePath}/certifications/${encodeURIComponent(cert.id)}`, payload);
      } else {
        await api.post(`${basePath}/certifications`, payload);
      }
      onSaved();
    } catch (e) {
      setMsg(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ModalShell title={cert ? "編輯認證" : "新增認證"} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <ModalField label="認證項目 *" value={form.cert_name} onChange={(v) => setForm((f) => ({ ...f, cert_name: v }))} placeholder="電子鎖安裝認證" />
        <ModalField label="品牌" value={form.brand} onChange={(v) => setForm((f) => ({ ...f, brand: v }))} placeholder="Yale" />
        <div className="flex gap-3">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">取得日期</span>
            <input type="date" value={form.obtained_at} onChange={(e) => setForm((f) => ({ ...f, obtained_at: e.target.value }))} className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none" />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">到期日期</span>
            <input type="date" value={form.expires_at} onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value }))} className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none" />
          </label>
        </div>
      </div>
      {msg && <p className="mt-3 text-[13px] text-red-600">{msg}</p>}
      <ModalActions busy={busy} onClose={onClose} onSave={save} saveLabel="儲存" />
    </ModalShell>
  );
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-bold text-[var(--text-primary)]">{title}</h2>
        {children}
      </div>
    </div>
  );
}

function ModalField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)]" />
    </label>
  );
}

function ModalActions({ busy, onClose, onSave, saveLabel }: { busy: boolean; onClose: () => void; onSave: () => void; saveLabel: string }) {
  return (
    <div className="mt-5 flex justify-end gap-2">
      <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50">
        取消
      </button>
      <button type="button" onClick={onSave} disabled={busy} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50">
        {busy ? "儲存中…" : saveLabel}
      </button>
    </div>
  );
}
