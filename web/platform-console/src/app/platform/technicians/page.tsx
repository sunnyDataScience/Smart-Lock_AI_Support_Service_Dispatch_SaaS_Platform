"use client";

// CR-0114 §8 追補收尾 — 平台 console 師傅管理(自品牌 /technicians 移植)。
// 裁決 1:師傅身分管理全歸平台方。清單(跨品牌 authority)+ 搜尋 + 新增 +
// 連詳情 + 生命週期動作。管理職權(建立/編輯/認證)品牌端已收乾淨,只在此。
// UAT W6-2:文案接 i18n(platform.technicians namespace)。

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
import { useActionDialog } from "@/components/ui/ActionDialog";
import { useToast } from "@/components/ui/Toast";
import { useTranslations } from "@/components/i18n/LocaleProvider";

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
  // CR-0195：KYC 必要文件（身分證正反面）是否齊全。後端即時算，不是 DB 欄位。
  kyc_docs_complete: boolean;
  kyc_missing_doc_types: string[];
}

const STATUS_CLS: Record<TechStatus, string> = {
  pending_approval: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)] border-[var(--badge-warn-fg)]/25",
  active: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)] border-[var(--badge-success-fg)]/25",
  suspended: "bg-[var(--badge-danger-bg)] text-[var(--badge-danger-fg)] border-[var(--badge-danger-fg)]/25",
  rejected: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
  terminated: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
  inactive: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)] border-[var(--border)]",
};

// 每個狀態可執行的生命週期動作(對齊後端狀態機 _ALLOWED_TRANSITIONS)。
// labelKey 指 platform.technicians.action.*(inactive 的 reactivate 顯示「啟用」)。
type Action = "onboard-approve" | "onboard-reject" | "suspend" | "reactivate" | "terminate";
const ACTIONS: Record<TechStatus, { action: Action; labelKey: string; danger?: boolean }[]> = {
  pending_approval: [
    { action: "onboard-approve", labelKey: "approve" },
    { action: "onboard-reject", labelKey: "reject", danger: true },
  ],
  active: [
    { action: "suspend", labelKey: "suspend", danger: true },
    { action: "terminate", labelKey: "terminate", danger: true },
  ],
  suspended: [
    { action: "reactivate", labelKey: "reactivate" },
    { action: "terminate", labelKey: "terminate", danger: true },
  ],
  rejected: [{ action: "terminate", labelKey: "terminate", danger: true }],
  inactive: [
    { action: "reactivate", labelKey: "activate" },
    { action: "terminate", labelKey: "terminate", danger: true },
  ],
  terminated: [],
};

const FILTERS: (TechStatus | "")[] = ["", "pending_approval", "active", "suspended"];

export default function PlatformTechniciansPage() {
  const actionDialog = useActionDialog();
  const { toast } = useToast();
  const t = useTranslations("platform.technicians");
  const tc = useTranslations("platform.common");
  const tf = useTranslations("platform.fields");
  const [filter, setFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");
  const [rows, setRows] = useState<PlatformTechnician[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [docsIncompleteOnly, setDocsIncompleteOnly] = useState(false);
  // 儀表板待審卡帶 `?status=pending_approval` 進來時要直接落在該分頁(不是「全部」)。
  // 讀 URL 前先不打 API,否則會先用 filter="" 撈一次全部、再因 setFilter 重撈,
  // 使用者會看到清單閃一下。慣例同 apply/page.tsx:129——純 client 頁直接讀
  // window.location,不用 useSearchParams(那個要包 Suspense 才能 prerender)。
  const [urlFilterRead, setUrlFilterRead] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filter) params.set("status", filter);
      if (keyword.trim()) params.set("q", keyword.trim());
      const qs = params.toString();
      const res = await api.get<{ data: PlatformTechnician[] }>(
        `/api/v1/platform/technicians${qs ? `?${qs}` : ""}`,
      );
      setRows(res.data);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }, [filter, keyword]);

  useEffect(() => {
    const s = new URLSearchParams(window.location.search).get("status") ?? "";
    // 只認 FILTERS 內的值——擋掉手打亂參數(如 ?status=deleted)讓分頁列全部反白、
    // 卻又真的把 status 送去後端的窘況。
    if (s && (FILTERS as string[]).includes(s)) setFilter(s);
    setUrlFilterRead(true);
  }, []);

  useEffect(() => {
    if (urlFilterRead) load();
  }, [load, urlFilterRead]);

  // CR-0195「文件未齊」篩選：與 status 疊加。純前端過濾——清單資料本來就帶
  // kyc_docs_complete，多開一個後端參數只會讓兩邊的判準有第二個來源。
  const visibleRows = docsIncompleteOnly
    ? rows.filter((r) => !r.kyc_docs_complete)
    : rows;

  async function runAction(
    tech: PlatformTechnician,
    action: Action,
    label: string,
    danger?: boolean,
  ) {
    let body: Record<string, unknown> = {};
    if (action === "onboard-approve" && !tech.kyc_docs_complete) {
      // CR-0195 條件式核准：文件不齊時後端會 422，除非顯式承認。這裡不是「多問
      // 一句」而已——填的理由會落進 lifecycle event 的 reason 永久留存，是日後
      // 要說明「為何未驗證身分就放行」時唯一的依據。
      const missing = tech.kyc_missing_doc_types
        .map((d) => t(`kycDocType.${d}`))
        .join(t("listSeparator"));
      const reason = await actionDialog.open({
        title: t("conditionalApproveTitle", { name: tech.name }),
        danger: true,
        confirmLabel: t("conditionalApproveConfirm"),
        input: {
          label: t("conditionalReasonLabel"),
          minLength: 10,
          hint: t("conditionalReasonHint", { missing }),
        },
      });
      if (reason === null) return;
      body = {
        conditional: true,
        conditional_reason: typeof reason === "string" ? reason : "",
      };
    } else if (action !== "onboard-approve") {
      const reason = await actionDialog.open({
        title: t("actionDialogTitle", { action: label, name: tech.name }),
        danger,
        confirmLabel: label,
        input: {
          label: t("reasonLabel", { action: label }),
          minLength: 3,
          hint: t("reasonHint"),
        },
      });
      if (reason === null) return;
      body = { reason: typeof reason === "string" ? reason : "" };
    }
    setBusyId(tech.id);
    try {
      await api.post(`/api/v1/platform/technicians/${tech.id}:${action}`, body);
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此師傅的舊清單
      await load();
      toast({ title: t("actionDone", { action: label, name: tech.name }), variant: "success" });
    } catch (err) {
      toast({
        title: t("actionFailed", { action: label }),
        description: friendlyError(err),
        variant: "error",
      });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{t("subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        >
          <Plus className="h-4 w-4" aria-hidden />
          {t("addNew")}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((value) => (
          <button
            key={value || "all"}
            type="button"
            onClick={() => setFilter(value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              filter === value
                ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
            }`}
          >
            {value === "" ? tc("all") : t(`status.${value}`)}
          </button>
        ))}
        {/* CR-0195：與 status 是不同軸的篩選（可疊加）。資料清單本來就帶
            kyc_docs_complete，故在前端過濾即可，不需要另一個後端參數。 */}
        <button
          type="button"
          onClick={() => setDocsIncompleteOnly((v) => !v)}
          aria-pressed={docsIncompleteOnly}
          className={`rounded-lg border px-3 py-1.5 text-sm transition ${
            docsIncompleteOnly
              ? "border-[var(--badge-warn-fg)] bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)]"
              : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
          }`}
        >
          {t("docsIncompleteFilter")}
        </button>
        <div className="ml-auto flex h-[38px] w-[260px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
          <Search className="h-4 w-4 text-[var(--text-secondary)]" aria-hidden />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="flex-1 bg-transparent text-sm outline-none"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-[var(--badge-danger-fg)]/25 bg-[var(--badge-danger-bg)] px-4 py-3 text-sm text-[var(--badge-danger-fg)]">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">{tc("loading")}</p>
      ) : visibleRows.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-10 text-center text-sm text-[var(--text-secondary)]">
          {t("emptyList")}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {visibleRows.map((tech) => (
            <div
              key={tech.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/platform/technicians/${tech.id}`}
                      className="text-base font-semibold text-[var(--primary)] hover:underline"
                    >
                      {tech.name || t("unnamed")}
                    </Link>
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_CLS[tech.status]}`}>
                      {t(`status.${tech.status}`)}
                    </span>
                    {!tech.is_active && tech.status === "active" && (
                      <span className="rounded-md border border-[var(--badge-warn-fg)]/25 bg-[var(--badge-warn-bg)] px-2 py-0.5 text-xs text-[var(--badge-warn-fg)]">
                        {t("loginNotSynced")}
                      </span>
                    )}
                    {/* CR-0195：已核准卻文件未齊＝條件式核准的待補件對象，
                        這是「誰還沒補」在畫面上唯一看得到的地方。 */}
                    {!tech.kyc_docs_complete && (
                      <span
                        className="rounded-md border border-[var(--badge-warn-fg)]/25 bg-[var(--badge-warn-bg)] px-2 py-0.5 text-xs text-[var(--badge-warn-fg)]"
                        title={tech.kyc_missing_doc_types
                          .map((d) => t(`kycDocType.${d}`))
                          .join(t("listSeparator"))}
                      >
                        {t("docsIncompleteBadge")}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-sm text-[var(--text-secondary)] sm:grid-cols-2">
                    <span>{tf("phone")}{tc("colon")}{tech.phone || "—"}</span>
                    <span>{tf("email")}{tc("colon")}{tech.email || "—"}</span>
                    {tech.capabilities.length > 0 && (
                      <span className="sm:col-span-2">
                        {t("skills")}{tc("colon")}{tech.capabilities.join("、")}
                      </span>
                    )}
                    {tech.service_regions.length > 0 && (
                      <span className="sm:col-span-2">
                        {t("regions")}{tc("colon")}{tech.service_regions.join("、")}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link
                    href={`/platform/technicians/${tech.id}`}
                    className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
                  >
                    {tc("details")}
                  </Link>
                  {ACTIONS[tech.status].map((a) => (
                    <button
                      key={a.action}
                      type="button"
                      disabled={busyId === tech.id}
                      onClick={() => runAction(tech, a.action, t(`action.${a.labelKey}`), a.danger)}
                      className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition disabled:opacity-50 ${
                        a.danger
                          ? "border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
                          : "bg-[var(--primary)] text-white hover:opacity-90"
                      }`}
                    >
                      {t(`action.${a.labelKey}`)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {createOpen && (
        <CreateTechnicianModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            setFilter("pending_approval");
            load();
          }}
        />
      )}
    </div>
  );
}

function CreateTechnicianModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const t = useTranslations("platform.technicians");
  const tc = useTranslations("platform.common");
  const [form, setForm] = useState({ name: "", phone: "", email: "", regions: "", skills: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const splitCsv = (s: string) =>
    s.split(/[,，、]/).map((x) => x.trim()).filter(Boolean);

  async function submit() {
    if (!form.name.trim()) {
      setMsg(t("nameRequired"));
      return;
    }
    if (splitCsv(form.regions).length === 0) {
      setMsg(t("regionsRequired"));
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/api/v1/platform/technicians", {
        display_name: form.name.trim(),
        coverage_areas: splitCsv(form.regions),
        phone: form.phone.trim() || undefined,
        email: form.email.trim() || undefined,
        capabilities: splitCsv(form.skills),
      });
      cacheInvalidate("GET:"); // 新師傅才會立即出現在清單(清 30s GET 舊快取)
      onCreated();
    } catch (e) {
      setMsg(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-lg">
        <h2 className="text-lg font-bold text-[var(--text-primary)]">{t("addNew")}</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{t("createHint")}</p>
        <div className="mt-4 flex flex-col gap-3">
          <Field label={t("fieldName")} value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} placeholder={t("namePlaceholder")} />
          <div className="flex gap-3">
            <Field label={t("fieldPhone")} value={form.phone} onChange={(v) => setForm((f) => ({ ...f, phone: v }))} placeholder="0912345678" className="flex-1" />
            <Field label={t("fieldEmail")} value={form.email} onChange={(v) => setForm((f) => ({ ...f, email: v }))} placeholder={t("emailPlaceholder")} className="flex-1" />
          </div>
          <Field label={t("fieldRegions")} value={form.regions} onChange={(v) => setForm((f) => ({ ...f, regions: v }))} placeholder={t("regionsPlaceholder")} />
          <Field label={t("fieldSkills")} value={form.skills} onChange={(v) => setForm((f) => ({ ...f, skills: v }))} placeholder="Yale, Dormakaba" />
        </div>
        {msg && <p className="mt-3 text-[13px] text-[var(--status-danger)]">{msg}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
          >
            {tc("cancel")}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {busy ? t("creating") : t("createSubmit")}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  className,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <label className={`flex flex-col gap-1 text-sm ${className ?? ""}`}>
      <span className="text-[var(--text-secondary)]">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)]"
      />
    </label>
  );
}
