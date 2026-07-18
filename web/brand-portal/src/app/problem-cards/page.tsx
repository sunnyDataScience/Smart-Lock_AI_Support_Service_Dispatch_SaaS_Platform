"use client";

import { Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import ProblemCardsTable from "@/components/problem-cards/ProblemCardsTable";
import { api, resolveTenantId, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { LOCK_BRANDS } from "@/lib/constants/brands";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";
import { useEffect, useMemo, useState } from "react";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardEnvelope = components["schemas"]["ProblemCardEnvelope"];
type Urgency = components["schemas"]["Urgency"];

/**
 * 客服手建問題卡 payload（UAT P1-1）。
 * api.generated 的 ProblemCardCreateRequest 綁 conversation_id（AI／對話入口專用）；
 * 手建入口（電話等非 LINE 進線）無對話，後端 create 已放寬收 location 與客戶欄位，
 * 依 types/api.local.ts 慣例本地宣告實際送出的形狀。
 */
interface ManualProblemCardCreateRequest {
  brand: string;
  model?: string;
  symptom: string;
  urgency: Urgency;
  location?: string;
  customer_name: string;
  customer_phone: string;
}

function formatProblemCardError(e: unknown): string {
  return friendlyError(e);
}

const PAGE_SIZE = 20;

const FILTER_KEYS = ["status", "urgency", "brand"] as const;

export default function ProblemCardsPage() {
  const t = useTranslations("pages.problemCards");
  const tFilters = useTranslations("pages.problemCards.filters");
  const router = useRouter();

  // CR-0002-α：遷移至 tenant-scoped v2 端點
  const tenantId = resolveTenantId();

  // UAT P1-1：客服手建問題卡入口
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createToast, setCreateToast] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [urgencyFilter, setUrgencyFilter] = useState<string>("");
  const [brandFilter, setBrandFilter] = useState<string>("");
  const [periodFilter, setPeriodFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (statusFilter) p.set("status", statusFilter);
    if (urgencyFilter) p.set("urgency", urgencyFilter);
    if (brandFilter) p.set("brand", brandFilter);
    if (sourceFilter) p.set("source", sourceFilter);
    if (keyword.trim()) p.set("keyword", keyword.trim());
    if (periodFilter) {
      const days = parseInt(periodFilter, 10);
      if (!Number.isNaN(days)) {
        const since = new Date(Date.now() - days * 24 * 3600 * 1000);
        p.set("created_after", since.toISOString());
      }
    }
    const qs = p.toString();
    return qs ? `?${qs}` : "";
  }, [statusFilter, urgencyFilter, brandFilter, periodFilter, sourceFilter, keyword]);

  const { items, cursor, hasMore, loading, error, loadMore } = usePaginatedFetch<ProblemCard>({
    path: `/tenants/${encodeURIComponent(tenantId)}/problem-cards${queryString}`,
    pageSize: PAGE_SIZE,
    formatError: formatProblemCardError,
  });

  const brandOptions = useMemo(() => {
    const set = new Set<string>();
    items.forEach((c: any) => {
      if (c.brand) set.add(c.brand);
    });
    return Array.from(set).sort();
  }, [items]);

  // 手建 modal 品牌下拉：正典品牌清單 ∪ 現有卡片出現過的品牌（datalist 仍可自由輸入）
  const createBrandOptions = useMemo(() => {
    const set = new Set<string>(LOCK_BRANDS.map((b) => b.value));
    brandOptions.forEach((b) => set.add(b));
    return Array.from(set).sort();
  }, [brandOptions]);

  useEffect(() => {
    if (!createToast) return;
    const timer = setTimeout(() => setCreateToast(null), 2400);
    return () => clearTimeout(timer);
  }, [createToast]);

  const handleCreate = async (req: ManualProblemCardCreateRequest) => {
    setCreating(true);
    setCreateError(null);
    try {
      const res = await api.post<ProblemCardEnvelope>(
        tenantPath("/problem-cards"),
        req,
      );
      const created = res.data;
      setCreateOpen(false);
      setCreateToast(t("createModal.created"));
      if (created?.id) {
        // 手建後下一步多為確認／報價，直接帶到詳情頁接續作業
        router.push(`/problem-cards/${encodeURIComponent(created.id)}`);
      }
    } catch (e) {
      setCreateError(friendlyError(e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-[var(--text-secondary)]">
              {t("breadcrumb")}
            </span>
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">{t("totalLabelPrefix")}</span>
              <span className="text-[13px] font-bold text-[var(--text-primary)]">
                {loading && items.length === 0 ? "—" : items.length}
              </span>
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                {hasMore ? t("totalCardsMore") : t("totalCards")}
              </span>
            </div>
            {/* UAT P1-1：客服手建問題卡（電話等非 LINE 進線） */}
            <button
              onClick={() => {
                setCreateError(null);
                setCreateOpen(true);
              }}
              className="inline-flex items-center gap-1 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              {t("createButton")}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("status")}</option>
            <option value="incomplete">未完成</option>
            <option value="complete">已完成</option>
            <option value="resolved">已處理</option>
          </select>

          <select
            value={urgencyFilter}
            onChange={(e) => setUrgencyFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("urgency")}</option>
            <option value="low">低</option>
            <option value="normal">一般</option>
            <option value="high">高</option>
            <option value="critical">緊急</option>
          </select>

          <select
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("brand")}</option>
            {brandOptions.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>

          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("dateRange")}</option>
            <option value="7">最近 7 天</option>
            <option value="30">最近 30 天</option>
            <option value="90">最近 90 天</option>
          </select>

          {/* CR-0022：來源篩選 — 「AI 草擬」即 LINE agent 轉真人待客服人審轉工單的佇列 */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("source")}</option>
            <option value="ai_line">AI 草擬（待轉工單）</option>
            <option value="human">客服手建</option>
          </select>

          <div className="flex h-9 flex-1 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="flex-1 bg-transparent text-[13px] outline-none"
            />
          </div>
        </div>

        <main className="flex-1 overflow-auto bg-[var(--bg-page)] px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {t("loadFailed", { error })}
            </div>
          )}

          <ProblemCardsTable items={items} loading={loading} />

          {hasMore && items.length > 0 && (
            <div className="mt-4 flex justify-center">
              <button
                disabled={loading}
                onClick={loadMore}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? t("loadingMore") : t("loadMore")}
              </button>
            </div>
          )}
        </main>
      </div>

      {createOpen && (
        <CreateProblemCardModal
          brandOptions={createBrandOptions}
          pending={creating}
          error={createError}
          onCancel={() => !creating && setCreateOpen(false)}
          onSubmit={handleCreate}
        />
      )}

      {createToast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {createToast}
        </div>
      )}
    </div>
  );
}

const URGENCY_VALUES: readonly Urgency[] = ["low", "medium", "high"];

// UAT P1-1：客服手建問題卡 modal（客戶姓名／電話／品牌／型號／症狀／服務地址）
function CreateProblemCardModal({
  brandOptions,
  pending,
  error,
  onCancel,
  onSubmit,
}: {
  brandOptions: string[];
  pending: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (req: ManualProblemCardCreateRequest) => Promise<void>;
}) {
  const t = useTranslations("pages.problemCards.createModal");
  const tUrgency = useTranslations("urgency");
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [symptom, setSymptom] = useState("");
  const [urgency, setUrgency] = useState<Urgency>("medium");
  const [location, setLocation] = useState("");

  const canSubmit =
    customerName.trim().length > 0 &&
    customerPhone.trim().length > 0 &&
    symptom.trim().length > 0 &&
    !pending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const req: ManualProblemCardCreateRequest = {
      customer_name: customerName.trim(),
      customer_phone: customerPhone.trim(),
      brand: brand.trim(),
      symptom: symptom.trim(),
      urgency,
    };
    if (model.trim()) req.model = model.trim();
    if (location.trim()) req.location = location.trim();
    void onSubmit(req);
  };

  const inputCls =
    "w-full rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-70";

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        className="max-h-[90vh] w-full max-w-[520px] overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex items-center gap-2">
          <Plus className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>
        <p className="mb-4 text-[12px] text-[var(--text-secondary)]">{t("hint")}</p>

        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                {t("customerName")} <span className="text-[var(--error)]">*</span>
              </span>
              <input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                disabled={pending}
                maxLength={80}
                className={inputCls}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                {t("customerPhone")} <span className="text-[var(--error)]">*</span>
              </span>
              <input
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                disabled={pending}
                maxLength={30}
                placeholder="09xx-xxx-xxx"
                className={inputCls}
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">{t("brand")}</span>
              <input
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                disabled={pending}
                maxLength={50}
                list="pc-create-brand-options"
                placeholder={t("brandPlaceholder")}
                className={inputCls}
              />
              <datalist id="pc-create-brand-options">
                {brandOptions.map((b) => (
                  <option key={b} value={b} />
                ))}
              </datalist>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">{t("model")}</span>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={pending}
                maxLength={100}
                placeholder={t("modelPlaceholder")}
                className={inputCls}
              />
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("symptom")} <span className="text-[var(--error)]">*</span>
            </span>
            <textarea
              value={symptom}
              onChange={(e) => setSymptom(e.target.value)}
              disabled={pending}
              rows={3}
              maxLength={1000}
              placeholder={t("symptomPlaceholder")}
              className={`${inputCls} resize-none`}
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">{t("urgency")}</span>
              <select
                value={urgency}
                onChange={(e) => setUrgency(e.target.value as Urgency)}
                disabled={pending}
                className={inputCls}
              >
                {URGENCY_VALUES.map((v) => (
                  <option key={v} value={v}>
                    {tUrgency(v)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">{t("location")}</span>
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                disabled={pending}
                maxLength={255}
                placeholder={t("locationPlaceholder")}
                className={inputCls}
              />
            </label>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            type="button"
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            type="button"
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
