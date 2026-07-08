"use client";

// CR-0114 §8 追補收尾 — 平台 console 師傅詳情（身分域管理）。
// 個人資料 + 編輯（含等級）+ 認證 CRUD + 生命週期歷史 + 生命週期動作。
// 排班/獎懲屬品牌營運（per-brand 工單/財務），不在跨品牌平台視角 —— 故不含。
// 內部工具 → 文案直接繁中。

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronLeft, Eye, FileText, Pencil, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { cacheInvalidate } from "@shared/lib/cache";

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

// ── KYC 審核資料（CR-0115 S7；§8-3 預設遮罩、reveal 取全值寫稽核）──────────
interface KycReview {
  profile: {
    years_experience: number | null;
    bio: string | null;
    vehicle_type: string | null;
    availability_note: string | null;
    emergency_contact_name: string | null;
    emergency_contact_phone: string | null;
    terms_accepted_at: string | null;
  };
  kyc: {
    has_national_id: boolean;
    national_id_last3: string | null;
    bank_code: string | null;
    has_bank_account: boolean;
    bank_account_last4: string | null;
    birth_date: string | null;
    address: string | null;
    tax_id: string | null;
  } | null;
  documents: RegistrationDocument[];
}

interface RegistrationDocument {
  id: string;
  doc_type: string;
  filename: string | null;
  content_type: string;
  size_bytes: number;
  created_at: string | null;
}

const DOC_TYPE_LABEL: Record<string, string> = {
  id_front: "身分證正面",
  id_back: "身分證反面",
  license: "證照掃描",
  insurance: "保險證明／良民證",
};

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
  const [kyc, setKyc] = useState<KycReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [certEdit, setCertEdit] = useState<Certification | "new" | null>(null);

  const base = `/api/v1/platform/technicians/${encodeURIComponent(id)}`;

  const load = useCallback(async () => {
    setError(null);
    try {
      // 主檔/認證/歷史三者任一失敗即整頁錯誤(核心資料);KYC 另外 allSettled
      // 取,單獨失敗只讓該區塊消失、不炸掉整頁審核。
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

      const kyc = await api
        .get<{ data: KycReview }>(`${base}/kyc`)
        .then((k) => k.data ?? null)
        .catch(() => null);
      setKyc(kyc);
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
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此認證的舊資料
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

          {/* KYC 審核資料（CR-0115 S7）*/}
          {kyc && <KycSection basePath={base} kyc={kyc} />}

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
                      {ev.event_type === "kyc_reveal" ? (
                        // CR-0115 S7:非狀態轉移的稽核事件(敏感資料揭露)
                        <span className="font-medium text-amber-700">檢視敏感資料全值</span>
                      ) : (
                        <span className="font-medium text-[var(--text-primary)]">
                          {STATUS_LABEL[ev.previous_status ?? ""] ?? ev.previous_status ?? "—"} → {STATUS_LABEL[ev.new_status ?? ""] ?? ev.new_status}
                        </span>
                      )}
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

// ── KYC 審核資料（CR-0115 S7）────────────────────────────────────────────────
// §8-3 (a)：預設遮罩顯示；「顯示完整資料」打 :reveal（後端寫稽核）。
// 文件實體走授權 fetch → blob 內嵌預覽（img/iframe），不經公開 URL。

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function KycSection({ basePath, kyc }: { basePath: string; kyc: KycReview }) {
  const [revealed, setRevealed] = useState<{ national_id: string | null; bank_account: string | null } | null>(null);
  const [revealBusy, setRevealBusy] = useState(false);
  const [revealErr, setRevealErr] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ url: string; contentType: string; label: string } | null>(null);
  const [previewBusy, setPreviewBusy] = useState<string | null>(null);
  // 目前 blob URL 存 ref,unmount / 換頁時保證 revoke(避免記憶體洩漏)。
  const previewUrlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  const p = kyc.profile;
  const k = kyc.kyc;
  const hasSensitive = !!k && (k.has_national_id || k.has_bank_account);

  async function reveal() {
    if (revealBusy) return;
    setRevealBusy(true);
    setRevealErr(null);
    try {
      const res = await api.post<{ data: { national_id: string | null; bank_account: string | null } }>(
        `${basePath}/kyc:reveal`,
      );
      setRevealed(res.data);
    } catch (e) {
      setRevealErr(friendlyError(e));
    } finally {
      setRevealBusy(false);
    }
  }

  async function openPreview(doc: RegistrationDocument) {
    if (previewBusy) return;
    setPreviewBusy(doc.id);
    try {
      // 走 api.fetchBlob:共用 401 → refresh → retry 鏈,不繞過 token 續期。
      const { blob } = await api.fetchBlob(`${basePath}/documents/${encodeURIComponent(doc.id)}`);
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(blob);
      previewUrlRef.current = url;
      setPreview({
        url,
        contentType: doc.content_type,
        label: DOC_TYPE_LABEL[doc.doc_type] ?? doc.doc_type,
      });
    } catch (e) {
      window.alert(friendlyError(e));
    } finally {
      setPreviewBusy(null);
    }
  }

  function closePreview() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreview(null);
  }

  const maskedNationalId = k?.has_national_id
    ? `•••••••${k.national_id_last3 ?? ""}`
    : null;
  const maskedBankAccount = k?.has_bank_account
    ? `${k.bank_code ? `${k.bank_code} ` : ""}••••${k.bank_account_last4 ?? ""}`
    : null;

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[var(--primary)]" aria-hidden />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">KYC 審核資料</h2>
        </div>
        {hasSensitive && !revealed && (
          <button
            type="button"
            onClick={reveal}
            disabled={revealBusy}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-primary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
          >
            <Eye className="h-3.5 w-3.5" aria-hidden />
            {revealBusy ? "解密中…" : "顯示完整資料"}
          </button>
        )}
        {revealed && (
          <span className="text-xs text-amber-600">已顯示完整資料（本次揭露已寫入稽核）</span>
        )}
      </div>
      {revealErr && <p className="mb-3 text-[13px] text-red-600">{revealErr}</p>}

      <div className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
        <Info label="從業年資" value={p.years_experience != null ? `${p.years_experience} 年` : "—"} />
        <Info label="交通工具" value={p.vehicle_type || "—"} />
        <Info label="可服務時段" value={p.availability_note || "—"} />
        <Info
          label="緊急聯絡人"
          value={p.emergency_contact_name ? `${p.emergency_contact_name}（${p.emergency_contact_phone || "—"}）` : "—"}
        />
        <Info
          label="條款同意時間"
          value={p.terms_accepted_at ? p.terms_accepted_at.slice(0, 16).replace("T", " ") : "未同意"}
        />
        {p.bio && <Info label="自我介紹" value={p.bio} span />}
      </div>

      <h3 className="mb-2 mt-5 text-sm font-semibold text-[var(--text-primary)]">敏感資料（加密保存）</h3>
      {!k ? (
        <p className="text-sm text-[var(--text-secondary)]">師傅尚未提供敏感 PII（可於核准前補件）</p>
      ) : (
        <div className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          <Info label="身分證字號" value={revealed?.national_id ?? maskedNationalId ?? "—"} />
          <Info label="生日" value={k.birth_date ?? "—"} />
          <Info
            label="撥款帳戶"
            value={
              revealed?.bank_account
                ? `${k.bank_code ? `${k.bank_code} ` : ""}${revealed.bank_account}`
                : maskedBankAccount ?? "—"
            }
          />
          <Info label="統一編號" value={k.tax_id ?? "—"} />
          <Info label="通訊地址" value={k.address ?? "—"} span />
        </div>
      )}

      <h3 className="mb-2 mt-5 text-sm font-semibold text-[var(--text-primary)]">證件文件</h3>
      {kyc.documents.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">尚未上傳文件（可於核准前補件）</p>
      ) : (
        <div className="flex flex-col divide-y divide-[var(--border)]">
          {kyc.documents.map((d) => (
            <div key={d.id} className="flex items-center gap-3 py-2.5">
              <FileText className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" aria-hidden />
              <div className="min-w-0 flex-1">
                <span className="text-sm font-medium text-[var(--text-primary)]">
                  {DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type}
                </span>
                <span className="ml-2 text-xs text-[var(--text-secondary)]">
                  {d.filename}（{fmtBytes(d.size_bytes)}）
                </span>
              </div>
              <button
                type="button"
                onClick={() => openPreview(d)}
                disabled={!!previewBusy}
                className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text-primary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
              >
                <Eye className="h-3.5 w-3.5" aria-hidden />
                {previewBusy === d.id ? "載入中…" : "預覽"}
              </button>
            </div>
          ))}
        </div>
      )}

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) closePreview();
          }}
        >
          <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl bg-[var(--bg-surface)] p-4 shadow-lg">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--text-primary)]">{preview.label}</h3>
              <button
                type="button"
                onClick={closePreview}
                className="rounded-lg border border-[var(--border)] px-3 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
              >
                關閉
              </button>
            </div>
            {preview.contentType.startsWith("image/") ? (
              // eslint-disable-next-line @next/next/no-img-element -- blob object URL 無法用 next/image
              <img src={preview.url} alt={preview.label} className="max-h-[75vh] w-full object-contain" />
            ) : (
              <iframe src={preview.url} title={preview.label} className="h-[75vh] w-full rounded-lg border border-[var(--border)]" />
            )}
          </div>
        </div>
      )}
    </section>
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
      cacheInvalidate("GET:"); // 編輯後變更立即反映（清 30s GET 舊快取）
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
      cacheInvalidate("GET:"); // 認證新增/編輯後立即反映（清 30s GET 舊快取）
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
