"use client";

// CR-0114 §8 追補收尾 — 平台 console 師傅管理（自品牌 /technicians 移植）。
// 裁決 1：師傅身分管理全歸平台方。清單（跨品牌 authority）+ 搜尋 + 新增 +
// 連詳情 + 生命週期動作。管理職權（建立/編輯/認證）品牌端已收乾淨,只在此。
// 內部工具 → 文案直接繁中,不入 i18n。

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { cacheInvalidate } from "@/lib/cache";
import { useActionDialog } from "@/components/ui/ActionDialog";
import { useToast } from "@/components/ui/Toast";

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

// 每個狀態可執行的生命週期動作（對齊後端狀態機 _ALLOWED_TRANSITIONS）
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
  { value: "", label: "全部" },
  { value: "pending_approval", label: "待審核" },
  { value: "active", label: "啟用中" },
  { value: "suspended", label: "已停權" },
];

export default function PlatformTechniciansPage() {
  const actionDialog = useActionDialog();
  const { toast } = useToast();
  const [filter, setFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");
  const [rows, setRows] = useState<PlatformTechnician[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

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
    load();
  }, [load]);

  async function runAction(
    tech: PlatformTechnician,
    action: Action,
    label: string,
    danger?: boolean,
  ) {
    let body: Record<string, string> = {};
    if (action !== "onboard-approve") {
      const reason = await actionDialog.open({
        title: `${label}「${tech.name}」`,
        danger,
        confirmLabel: label,
        input: { label: `${label}原因`, minLength: 3, hint: "至少 3 字,記入稽核" },
      });
      if (reason === null) return;
      body = { reason: typeof reason === "string" ? reason : "" };
    }
    setBusyId(tech.id);
    try {
      await api.post(`/api/v1/platform/technicians/${tech.id}:${action}`, body);
      cacheInvalidate("GET:"); // 清 30s GET 快取,否則 load() 讀到含此師傅的舊清單
      await load();
      toast({ title: `已${label}「${tech.name}」`, variant: "success" });
    } catch (err) {
      toast({ title: `${label}失敗`, description: friendlyError(err), variant: "error" });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">師傅管理</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            鎖匠師傅的註冊審核、生命週期與主檔管理。師傅平台全品牌共用，由平台方統一負責。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        >
          <Plus className="h-4 w-4" aria-hidden />
          新增師傅
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
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
        <div className="ml-auto flex h-[38px] w-[260px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
          <Search className="h-4 w-4 text-[var(--text-secondary)]" aria-hidden />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜尋姓名 / 電話 / Email"
            className="flex-1 bg-transparent text-sm outline-none"
          />
        </div>
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
                    <Link
                      href={`/platform/technicians/${tech.id}`}
                      className="text-base font-semibold text-[var(--primary)] hover:underline"
                    >
                      {tech.name || "（未命名）"}
                    </Link>
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
                <div className="flex flex-wrap gap-2">
                  <Link
                    href={`/platform/technicians/${tech.id}`}
                    className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))]"
                  >
                    詳情
                  </Link>
                  {ACTIONS[tech.status].map((a) => (
                    <button
                      key={a.action}
                      type="button"
                      disabled={busyId === tech.id}
                      onClick={() => runAction(tech, a.action, a.label, a.danger)}
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
  const [form, setForm] = useState({ name: "", phone: "", email: "", regions: "", skills: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const splitCsv = (s: string) =>
    s.split(/[,，、]/).map((x) => x.trim()).filter(Boolean);

  async function submit() {
    if (!form.name.trim()) {
      setMsg("姓名為必填");
      return;
    }
    if (splitCsv(form.regions).length === 0) {
      setMsg("服務區域為必填");
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
      cacheInvalidate("GET:"); // 新師傅才會立即出現在清單（清 30s GET 舊快取）
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
        <h2 className="text-lg font-bold text-[var(--text-primary)]">新增師傅</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          建立後狀態為「待審核」，需於清單核准後方可派工；登入密碼由師傅自助設定（忘記密碼）。
        </p>
        <div className="mt-4 flex flex-col gap-3">
          <Field label="姓名 *" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} placeholder="例：王大鎖" />
          <div className="flex gap-3">
            <Field label="電話" value={form.phone} onChange={(v) => setForm((f) => ({ ...f, phone: v }))} placeholder="0912345678" className="flex-1" />
            <Field label="Email" value={form.email} onChange={(v) => setForm((f) => ({ ...f, email: v }))} placeholder="（選填）" className="flex-1" />
          </div>
          <Field label="服務區域 *（逗號分隔）" value={form.regions} onChange={(v) => setForm((f) => ({ ...f, regions: v }))} placeholder="台北市, 新北市" />
          <Field label="專長品牌（逗號分隔，選填）" value={form.skills} onChange={(v) => setForm((f) => ({ ...f, skills: v }))} placeholder="Yale, Dormakaba" />
        </div>
        {msg && <p className="mt-3 text-[13px] text-red-600">{msg}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover,rgba(0,0,0,0.04))] disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "建立中…" : "建立師傅"}
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
