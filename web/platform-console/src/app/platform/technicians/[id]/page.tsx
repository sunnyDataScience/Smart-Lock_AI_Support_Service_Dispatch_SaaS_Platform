"use client";

// CR-0114 §8 追補收尾 — 平台 console 師傅詳情(身分域管理)。
// 個人資料 + 編輯(含等級)+ 認證 CRUD + 生命週期歷史 + 生命週期動作。
// UAT R2 W3-5/W3-6:KYC 區塊加「產生補件連結」(免 email 自助方案——連結由
// 管理員以 LINE/電話轉交師傅,師傅站 /upload-docs/{token} 公開消費)。
// 排班/獎懲屬品牌營運(per-brand 工單/財務),不在跨品牌平台視角 —— 故不含。
// UAT W6-2:原「內部工具文案直接繁中」決策撤回——全量接 i18n
// (platform.technicians.detail namespace;狀態沿用 platform.technicians.status)。

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronLeft, Eye, FileText, Link2, Pencil, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import BrandAuthorizationPanel from "@/components/technicians/BrandAuthorizationPanel";
import { cacheInvalidate } from "@/lib/cache";
import { useActionDialog } from "@/components/ui/ActionDialog";
import { useToast } from "@/components/ui/Toast";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { TranslateFn } from "@/lib/translate";

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

// ── KYC 審核資料(CR-0115 S7;§8-3 預設遮罩、reveal 取全值寫稽核)──────────
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

// i18n 已知鍵集合 —— 後端來的動態值只有落在集合內才走翻譯,否則原樣顯示
// (translate 缺 key 會回傳完整 path,直接餵 UI 會露出 "platform.…" 字串)。
const KNOWN_DOC_TYPES = new Set(["id_front", "id_back", "license", "insurance"]);
const KNOWN_STATUSES = new Set([
  "pending_approval",
  "active",
  "suspended",
  "rejected",
  "terminated",
  "inactive",
]);
const KNOWN_ACTOR_ROLES = new Set([
  "admin",
  "platform_admin",
  "operations_manager",
  "reviewer",
]);

const CERT_STATUS_CLS: Record<Certification["status"], string> = {
  valid: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25",
  expiring_soon: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25",
  expired: "bg-[var(--badge-danger-bg)] text-[var(--badge-danger-fg)] border-[var(--badge-danger-fg)]/25",
};

const LEVELS = ["S", "A", "B", "C"];

/** 師傅狀態顯示(沿用清單頁 platform.technicians.status.*;未知狀態原樣)。 */
function statusLabel(tt: TranslateFn, status: string | null): string {
  if (!status) return "—";
  return KNOWN_STATUSES.has(status) ? tt(`status.${status}`) : status;
}

/** 證件文件類型顯示(未知類型原樣)。 */
function docTypeLabel(td: TranslateFn, docType: string): string {
  return KNOWN_DOC_TYPES.has(docType) ? td(`kyc.docType.${docType}`) : docType;
}

// lifecycle 事件 reason 的機器句翻譯(technician_lifecycle_service 寫入
// "onboarding approved by <actor_role>" 英文機器句;其餘 reason 為自由文字原樣)
function humanizeEventReason(td: TranslateFn, raw: string): string {
  const m = raw.match(/^onboarding approved by (\S+)$/);
  if (m) {
    const actor = KNOWN_ACTOR_ROLES.has(m[1]) ? td(`lifecycle.actorRole.${m[1]}`) : m[1];
    return td("lifecycle.onboardApproved", { actor });
  }
  // CR-0195 條件式核准：後端寫的是 `[conditional|missing:a,b] <審核者填的理由>`。
  // 前綴是給機器讀的(可 grep 稽核)，但直接攤在畫面上等於把內部格式丟給使用者看，
  // 所以這裡拆開重組——缺件型別翻成中文，理由原樣保留。
  // [\s\S] 而非 /s flag——tsconfig target 低於 es2018，dotAll 不可用（TS1501）
  const c = raw.match(/^\[conditional\|missing:([^\]]*)\]\s*([\s\S]*)$/);
  if (c) {
    const missing = c[1]
      .split(",")
      .filter(Boolean)
      .map((d) => docTypeLabel(td, d.trim()))
      .join(td("listSeparator"));
    return td("lifecycle.onboardApprovedConditional", { missing, reason: c[2] });
  }
  return raw;
}

function fmtDate(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "—";
}

export default function PlatformTechnicianDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const actionDialog = useActionDialog();
  const { toast } = useToast();
  const tt = useTranslations("platform.technicians");
  const td = useTranslations("platform.technicians.detail");
  const tc = useTranslations("platform.common");
  const tf = useTranslations("platform.fields");
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
    const confirmed = await actionDialog.open({
      title: td("certs.deleteTitle", { name: cert.cert_name }),
      danger: true,
      confirmLabel: td("certs.deleteConfirm"),
    });
    if (confirmed === null) return;
    try {
      await api.delete(`${base}/certifications/${encodeURIComponent(cert.id)}`);
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此認證的舊資料
      await load();
      toast({ title: td("certs.deleteDone", { name: cert.cert_name }), variant: "success" });
    } catch (e) {
      toast({ title: td("certs.deleteFailed"), description: friendlyError(e), variant: "error" });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/platform/technicians"
        className="flex w-fit items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden />
        {td("back")}
      </Link>

      {error && (
        <div className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-4 py-3 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {loading && !tech ? (
        <p className="text-sm text-[var(--text-secondary)]">{tc("loading")}</p>
      ) : !tech ? (
        <p className="text-sm text-[var(--text-secondary)]">{td("notFound")}</p>
      ) : (
        <>
          {/* 個人資料 */}
          <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-[var(--text-primary)]">{tech.name}</h1>
                <span className="rounded-md border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                  {statusLabel(tt, tech.status)}
                </span>
                <span className="rounded-md bg-[var(--bg-page)] px-2 py-0.5 text-xs font-semibold text-[var(--text-secondary)]">
                  {td("levelBadge", { level: tech.level })}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setEditOpen(true)}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-primary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
              >
                <Pencil className="h-3.5 w-3.5" aria-hidden />
                {tc("edit")}
              </button>
            </div>
            <div className="mt-4 grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
              <Info label={tf("phone")} value={tech.phone || "—"} />
              <Info label={td("rating")} value={tech.rating.toFixed(1)} />
              <Info label={td("completedOrders")} value={String(tech.completed_orders_count ?? 0)} />
              <Info label={td("createdAt")} value={fmtDate(tech.created_at)} />
              <Info label={td("specialtyBrands")} value={tech.skills.length ? tech.skills.join(td("listSeparator")) : "—"} span />
              <Info label={tt("regions")} value={tech.service_areas.length ? tech.service_areas.join(td("listSeparator")) : "—"} span />
              {tech.authorized_brands && tech.authorized_brands.length > 0 && (
                <Info label={td("authorizedBrands")} value={tech.authorized_brands.join(td("listSeparator"))} span />
              )}
            </div>
          </section>

          {/* KYC 審核資料(CR-0115 S7)*/}
          {/* 補件連結(UAT R2 W3-5/W3-6 免 email 自助方案):僅「未核准(待審)
              或核心證件(身分證正反面)缺漏」時顯示產生按鈕。 */}
          {kyc && (
            <KycSection
              basePath={base}
              kyc={kyc}
              canIssueToken={
                // CR-0195：**先確認狀態在後端允許的值域內**，再談要不要顯示。
                // 原本這裡只有 OR 的後半段，於是 suspended/terminated 且缺件時
                // 也會渲染按鈕，點下去必得 409——UI 承諾了後端拒絕的事。
                // 業主 2026-07-30 回報的正是這個（那時 active 也被後端擋）。
                ["pending_approval", "active"].includes(tech.status ?? "") &&
                (tech.status === "pending_approval" ||
                  !["id_front", "id_back"].every((docType) =>
                    kyc.documents.some((d) => d.doc_type === docType),
                  ))
              }
            />
          )}

          {/* 技能認證矩陣 */}
          <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-[var(--text-primary)]">{td("certs.title")}</h2>
              <button
                type="button"
                onClick={() => setCertEdit("new")}
                className="flex items-center gap-1.5 rounded-lg border border-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary)] transition hover:bg-[var(--primary-subtle,rgba(59,130,246,0.08))]"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden />
                {td("certs.add")}
              </button>
            </div>
            {certs.length === 0 ? (
              <p className="py-6 text-center text-sm text-[var(--text-secondary)]">{td("certs.empty")}</p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--border)]">
                {certs.map((c) => (
                  <div key={c.id} className="flex items-center gap-4 py-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[var(--text-primary)]">{c.cert_name}</span>
                        <span className={`rounded-md border px-2 py-0.5 text-xs ${CERT_STATUS_CLS[c.status]}`}>
                          {td(`certs.status.${c.status}`)}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-[var(--text-secondary)]">
                        {c.brand && <span>{td("certs.brandMeta", { brand: c.brand })}</span>}
                        <span>{td("certs.obtainedMeta", { date: fmtDate(c.obtained_at) })}</span>
                        <span>{td("certs.expiresMeta", { date: fmtDate(c.expires_at) })}</span>
                      </div>
                    </div>
                    <button type="button" onClick={() => setCertEdit(c)} aria-label={td("certs.editAria")} className="text-[var(--text-secondary)] hover:text-[var(--primary)]">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button type="button" onClick={() => deleteCert(c)} aria-label={td("certs.deleteAria")} className="text-[var(--text-secondary)] hover:text-[var(--status-danger)]">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 生命週期歷史 */}

          {/* CR-0197：品牌授權名單維護——在此之前四站台都沒有這個畫面，
              營運只能打 API 或下 SQL，名單因此永遠補不齊、閘門也就永遠不能開。 */}
          <BrandAuthorizationPanel technicianId={id} />
          <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <h2 className="mb-4 text-base font-semibold text-[var(--text-primary)]">{td("lifecycle.title")}</h2>
            {events.length === 0 ? (
              <p className="py-6 text-center text-sm text-[var(--text-secondary)]">{td("lifecycle.empty")}</p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--border)]">
                {events.map((ev) => (
                  <div key={ev.id} className="flex items-start justify-between gap-4 py-3 text-sm">
                    <div>
                      {ev.event_type === "kyc_reveal" ? (
                        // CR-0115 S7:非狀態轉移的稽核事件(敏感資料揭露)
                        <span className="font-medium text-[var(--badge-warn-fg)]">{td("lifecycle.kycReveal")}</span>
                      ) : (
                        <span className="font-medium text-[var(--text-primary)]">
                          {statusLabel(tt, ev.previous_status)} → {statusLabel(tt, ev.new_status)}
                        </span>
                      )}
                      {ev.reason && (
                        <span className="text-[var(--text-secondary)]">
                          　{td("lifecycle.reason", { reason: humanizeEventReason(td, ev.reason) })}
                        </span>
                      )}
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
  const tc = useTranslations("platform.common");
  return (
    <div className={span ? "sm:col-span-2" : ""}>
      <span className="text-[var(--text-secondary)]">{label}{tc("colon")}</span>
      <span className="text-[var(--text-primary)]">{value}</span>
    </div>
  );
}

// ── KYC 審核資料(CR-0115 S7)────────────────────────────────────────────────
// §8-3 (a):預設遮罩顯示;「顯示完整資料」打 :reveal(後端寫稽核)。
// 文件實體走授權 fetch → blob 內嵌預覽(img/iframe),不經公開 URL。

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

// 補件連結指向師傅站(tech-portal)公開消費頁 /upload-docs/{token}。
// NEXT_PUBLIC_* 於 build 時烤入;未設 fallback 本機 tech-portal 埠位。
const TECH_PORTAL_BASE_URL =
  process.env.NEXT_PUBLIC_TECH_PORTAL_BASE_URL || "http://localhost:3001";

/** 一次性補件連結(token 明文僅回傳當下顯示,關閉即無法再取)。 */
interface IssuedUploadToken {
  link: string;
  expiresAt: string | null;
}

function KycSection({
  basePath,
  kyc,
  canIssueToken,
}: {
  basePath: string;
  kyc: KycReview;
  canIssueToken: boolean;
}) {
  const { toast } = useToast();
  const td = useTranslations("platform.technicians.detail");
  const tc = useTranslations("platform.common");
  const [revealed, setRevealed] = useState<{ national_id: string | null; bank_account: string | null } | null>(null);
  const [revealBusy, setRevealBusy] = useState(false);
  const [revealErr, setRevealErr] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ url: string; contentType: string; label: string } | null>(null);
  const [previewBusy, setPreviewBusy] = useState<string | null>(null);
  // 補件連結(UAT R2 W3-5/W3-6):issue-upload-token 回傳明文 token,組完整連結
  // 一次性顯示於 Modal;由管理員以 LINE/電話轉交師傅(免 email 設計)。
  const [issuedToken, setIssuedToken] = useState<IssuedUploadToken | null>(null);
  const [tokenBusy, setTokenBusy] = useState(false);
  const [copied, setCopied] = useState(false);
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
        label: docTypeLabel(td, doc.doc_type),
      });
    } catch (e) {
      toast({ title: td("kyc.previewFailed"), description: friendlyError(e), variant: "error" });
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

  // 產生補件連結:復用 technician_kyc_service.issue_upload_token(平台 admin
  // 端點)。回傳信封防禦處理({data:{...}} 或裸 {token,...} 皆可解)——
  // 型別未重生前不依賴 api.generated.ts。
  async function issueUploadToken() {
    if (tokenBusy) return;
    setTokenBusy(true);
    try {
      const res = await api.post<{
        data?: { token?: string; expires_at?: string | null };
        token?: string;
        expires_at?: string | null;
      }>(`${basePath}:issue-upload-token`);
      const payload = res.data ?? res;
      if (!payload.token) {
        toast({ title: td("uploadToken.failed"), variant: "error" });
        return;
      }
      setCopied(false);
      setIssuedToken({
        link: `${TECH_PORTAL_BASE_URL.replace(/\/+$/, "")}/upload-docs/${encodeURIComponent(payload.token)}`,
        expiresAt: payload.expires_at ?? null,
      });
    } catch (e) {
      toast({ title: td("uploadToken.failed"), description: friendlyError(e), variant: "error" });
    } finally {
      setTokenBusy(false);
    }
  }

  async function copyIssuedLink() {
    if (!issuedToken) return;
    try {
      await navigator.clipboard.writeText(issuedToken.link);
      setCopied(true);
    } catch {
      // 剪貼簿權限被拒(非 https 或未授權)→ 提示手動選取複製
      toast({ title: td("uploadToken.copyFailed"), variant: "error" });
    }
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
          <h2 className="text-base font-semibold text-[var(--text-primary)]">{td("kyc.title")}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canIssueToken && (
            <button
              type="button"
              onClick={issueUploadToken}
              disabled={tokenBusy}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary)] transition hover:bg-[var(--primary-subtle,rgba(59,130,246,0.08))] disabled:opacity-50"
            >
              <Link2 className="h-3.5 w-3.5" aria-hidden />
              {tokenBusy ? td("uploadToken.generating") : td("uploadToken.button")}
            </button>
          )}
          {hasSensitive && !revealed && (
            <button
              type="button"
              onClick={reveal}
              disabled={revealBusy}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-primary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
            >
              <Eye className="h-3.5 w-3.5" aria-hidden />
              {revealBusy ? td("kyc.revealing") : td("kyc.reveal")}
            </button>
          )}
          {revealed && (
            <span className="text-xs text-[var(--badge-warn-fg)]">{td("kyc.revealedNote")}</span>
          )}
        </div>
      </div>
      {revealErr && <p className="mb-3 text-[13px] text-[var(--status-danger)]">{revealErr}</p>}

      <div className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
        <Info
          label={td("kyc.yearsExperience")}
          value={p.years_experience != null ? td("kyc.yearsUnit", { years: p.years_experience }) : "—"}
        />
        <Info label={td("kyc.vehicleType")} value={p.vehicle_type || "—"} />
        <Info label={td("kyc.availabilityNote")} value={p.availability_note || "—"} />
        <Info
          label={td("kyc.emergencyContact")}
          value={p.emergency_contact_name ? `${p.emergency_contact_name}（${p.emergency_contact_phone || "—"}）` : "—"}
        />
        <Info
          label={td("kyc.termsAcceptedAt")}
          value={p.terms_accepted_at ? p.terms_accepted_at.slice(0, 16).replace("T", " ") : td("kyc.termsNotAccepted")}
        />
        {p.bio && <Info label={td("kyc.bio")} value={p.bio} span />}
      </div>

      <h3 className="mb-2 mt-5 text-sm font-semibold text-[var(--text-primary)]">{td("kyc.sensitiveTitle")}</h3>
      {!k ? (
        <p className="text-sm text-[var(--text-secondary)]">{td("kyc.noSensitive")}</p>
      ) : (
        <div className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          <Info label={td("kyc.nationalId")} value={revealed?.national_id ?? maskedNationalId ?? "—"} />
          <Info label={td("kyc.birthDate")} value={k.birth_date ?? "—"} />
          <Info
            label={td("kyc.bankAccount")}
            value={
              revealed?.bank_account
                ? `${k.bank_code ? `${k.bank_code} ` : ""}${revealed.bank_account}`
                : maskedBankAccount ?? "—"
            }
          />
          <Info label={td("kyc.taxId")} value={k.tax_id ?? "—"} />
          <Info label={td("kyc.address")} value={k.address ?? "—"} span />
        </div>
      )}

      <h3 className="mb-2 mt-5 text-sm font-semibold text-[var(--text-primary)]">{td("kyc.documentsTitle")}</h3>
      {kyc.documents.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">{td("kyc.noDocuments")}</p>
      ) : (
        <div className="flex flex-col divide-y divide-[var(--border)]">
          {kyc.documents.map((d) => (
            <div key={d.id} className="flex items-center gap-3 py-2.5">
              <FileText className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" aria-hidden />
              <div className="min-w-0 flex-1">
                <span className="text-sm font-medium text-[var(--text-primary)]">
                  {docTypeLabel(td, d.doc_type)}
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
                {previewBusy === d.id ? td("kyc.previewLoading") : td("kyc.preview")}
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
                {tc("close")}
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

      {/* 補件連結 Modal — token 明文一次性顯示;刻意不做點背景關閉
          (誤觸關閉即遺失連結,需重新產生),只留明確的關閉按鈕。 */}
      {issuedToken && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-lg">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">{td("uploadToken.modalTitle")}</h3>
            <p className="mt-1 text-xs text-[var(--badge-warn-fg)]">{td("uploadToken.oneTimeNote")}</p>

            <div className="mt-4 flex flex-col gap-1 text-sm">
              <span className="text-[var(--text-secondary)]">{td("uploadToken.linkLabel")}</span>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={issuedToken.link}
                  onFocus={(e) => e.currentTarget.select()}
                  className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 font-mono text-xs text-[var(--text-primary)] outline-none"
                />
                <button
                  type="button"
                  onClick={copyIssuedLink}
                  className="shrink-0 rounded-lg bg-[var(--primary)] px-3 py-2 text-sm font-semibold text-white transition hover:opacity-90"
                >
                  {copied ? td("uploadToken.copied") : td("uploadToken.copy")}
                </button>
              </div>
            </div>

            <p className="mt-3 text-xs text-[var(--text-secondary)]">
              {issuedToken.expiresAt
                ? td("uploadToken.expiresAt", {
                    time: issuedToken.expiresAt.slice(0, 16).replace("T", " "),
                  })
                : td("uploadToken.expiresUnknown")}
            </p>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">{td("uploadToken.deliverHint")}</p>

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setIssuedToken(null);
                  setCopied(false);
                }}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
              >
                {tc("close")}
              </button>
            </div>
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
  const td = useTranslations("platform.technicians.detail");
  const tc = useTranslations("platform.common");
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
      cacheInvalidate("GET:"); // 編輯後變更立即反映(清 30s GET 舊快取)
      onSaved();
    } catch (e) {
      setMsg(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ModalShell title={td("edit.title")} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <ModalField label={td("edit.fieldName")} value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} />
        <ModalField label={td("edit.fieldPhone")} value={form.phone} onChange={(v) => setForm((f) => ({ ...f, phone: v }))} />
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-[var(--text-secondary)]">{td("edit.fieldLevel")}</span>
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
        <ModalField label={td("edit.fieldSkills")} value={form.skills} onChange={(v) => setForm((f) => ({ ...f, skills: v }))} placeholder="Yale, Dormakaba" />
        <ModalField label={td("edit.fieldRegions")} value={form.regions} onChange={(v) => setForm((f) => ({ ...f, regions: v }))} placeholder={td("edit.regionsPlaceholder")} />
      </div>
      {msg && <p className="mt-3 text-[13px] text-[var(--status-danger)]">{msg}</p>}
      <ModalActions busy={busy} onClose={onClose} onSave={save} saveLabel={tc("save")} />
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
  const td = useTranslations("platform.technicians.detail");
  const tc = useTranslations("platform.common");
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
      setMsg(td("certs.nameRequired"));
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
      cacheInvalidate("GET:"); // 認證新增/編輯後立即反映(清 30s GET 舊快取)
      onSaved();
    } catch (e) {
      setMsg(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ModalShell title={cert ? td("certs.editTitle") : td("certs.addTitle")} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <ModalField label={td("certs.fieldName")} value={form.cert_name} onChange={(v) => setForm((f) => ({ ...f, cert_name: v }))} placeholder={td("certs.namePlaceholder")} />
        <ModalField label={td("certs.fieldBrand")} value={form.brand} onChange={(v) => setForm((f) => ({ ...f, brand: v }))} placeholder="Yale" />
        <div className="flex gap-3">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">{td("certs.fieldObtainedAt")}</span>
            <input type="date" value={form.obtained_at} onChange={(e) => setForm((f) => ({ ...f, obtained_at: e.target.value }))} className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none" />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="text-[var(--text-secondary)]">{td("certs.fieldExpiresAt")}</span>
            <input type="date" value={form.expires_at} onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value }))} className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none" />
          </label>
        </div>
      </div>
      {msg && <p className="mt-3 text-[13px] text-[var(--status-danger)]">{msg}</p>}
      <ModalActions busy={busy} onClose={onClose} onSave={save} saveLabel={tc("save")} />
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
  const tc = useTranslations("platform.common");
  return (
    <div className="mt-5 flex justify-end gap-2">
      <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50">
        {tc("cancel")}
      </button>
      <button type="button" onClick={onSave} disabled={busy} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50">
        {busy ? tc("saving") : saveLabel}
      </button>
    </div>
  );
}
