"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import { useKbCounts } from "@/hooks/useKbCounts";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CloudUpload, Trash2, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ManualsTable from "@/components/knowledge-base/ManualsTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type Manual = components["schemas"]["Manual"];
type ManualPage = components["schemas"]["ManualPage"];
type ManualEnvelope = components["schemas"]["ManualEnvelope"];

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const ACCEPTED_EXTENSION = ".pdf";

function formatErr(e: unknown): string {
  return friendlyError(e);
}

const PAGE_SIZE = 20;

const BRAND_OPTIONS = ["Yale", "Chatlock", "美樂", "Dormakaba", "Philips", "Kaadas"];

export default function ManualsPage() {
  const pathname = usePathname();
  const tKb = useTranslations("kb");
  const tTabs = useTranslations("kb.tabs");
  const tM = useTranslations("kb.manuals");

  const kbCounts = useKbCounts();
  const tabs = useMemo(
    () => [
      { label: tTabs("cases"), href: "/knowledge-base/cases", count: kbCounts.cases },
      { label: tTabs("manuals"), href: "/knowledge-base/manuals", count: kbCounts.manuals },
      { label: tTabs("sopDrafts"), href: "/knowledge-base/sop-drafts", count: kbCounts.sopDrafts },
    ],
    [tTabs, kbCounts],
  );
  const [brand, setBrand] = useState<string>("");
  const [confirmTarget, setConfirmTarget] = useState<Manual | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  // P2-W3: 改用 v2 /kb/documents?doc_type=manual（X-Tenant-ID 由 api.ts rawRequest 自動帶）
  // legacy /api/v1/knowledge-base/manuals 仍保留（Deprecation header，P3 前不移除）
  const {
    items: rawManualItems,
    cursor,
    hasMore,
    loading,
    error,
    loadMore,
    mutate: rawMutate,
  } = usePaginatedFetch<Record<string, unknown>>({
    path: "/kb/documents",
    pageSize: PAGE_SIZE,
    query: brand ? { doc_type: "manual", brand } : { doc_type: "manual" },
    queryKey: `brand=${brand}|v2`,
    formatError: formatErr,
  });

  // KBDocument → Manual 欄位展開
  const items = useMemo<Manual[]>(() => {
    return rawManualItems.map((doc) => {
      const meta = (doc.meta ?? {}) as Record<string, unknown>;
      return {
        id: doc.id as string,
        title: doc.title as string,
        brand: (meta.brand ?? "") as string,
        model: meta.model != null ? String(meta.model) : undefined,
        file_name: (meta.file_name ?? "") as string,
        file_size_bytes: Number(meta.file_size_bytes ?? 0),
        status: (meta.status ?? "processing") as Manual["status"],
        chunk_count: meta.chunk_count != null ? Number(meta.chunk_count) : null,
        created_at: (meta.created_at ?? new Date().toISOString()) as string,
      };
    });
  }, [rawManualItems]);

  // 包裝 mutate：讓呼叫端繼續用 Manual[] 型別
  const mutate = (fn: (prev: Manual[]) => Manual[]) => {
    rawMutate((prev) => {
      const manuals = prev.map((doc) => {
        const meta = (doc.meta ?? {}) as Record<string, unknown>;
        return {
          id: doc.id as string,
          title: doc.title as string,
          brand: (meta.brand ?? "") as string,
          model: meta.model != null ? String(meta.model) : undefined,
          file_name: (meta.file_name ?? "") as string,
          file_size_bytes: Number(meta.file_size_bytes ?? 0),
          status: (meta.status ?? "processing") as Manual["status"],
          chunk_count: meta.chunk_count != null ? Number(meta.chunk_count) : null,
          created_at: (meta.created_at ?? new Date().toISOString()) as string,
        };
      });
      return fn(manuals).map((m) => ({
        id: m.id,
        doc_type: "manual",
        title: m.title,
        tenant_scope: [],
        brand_scope: m.brand ? [m.brand] : [],
        project_scope: [],
        version: null,
        effective_date: null,
        meta: {
          brand: m.brand,
          model: m.model,
          file_name: m.file_name,
          file_size_bytes: m.file_size_bytes,
          status: m.status,
          chunk_count: m.chunk_count,
          created_at: m.created_at,
        },
      }));
    });
  };

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const handleDelete = async (manual: Manual) => {
    setDeletingId(manual.id);
    setDeleteError(null);
    try {
      // CR-0005 step 3/3 partial（業主 2026-06-04 拍 §8 HD-02=a 軟刪 + HD-03=a DB audit）
      // v2 DELETE manuals 從硬刪改軟刪（UPDATE deleted_at=NOW），audit log INSERT
      // 返回 204 無 body 無 shape 顧慮
      await api.delete(tenantPath(`/kb/documents/${encodeURIComponent(manual.id)}?doc_type=manual`));
      // optimistic local update via hook mutate (per Phase 3.3 backlog §C2)
      mutate((prev) => prev.filter((m) => m.id !== manual.id));
      setConfirmTarget(null);
      setToast(tM("deleteToast", { title: manual.title }));
    } catch (e) {
      setDeleteError(formatErr(e));
    } finally {
      setDeletingId(null);
    }
  };

  const handleUploaded = (manual: Manual) => {
    // upsert：去重後置頂（per Phase 3.3 backlog §C2 mutate 慣例）
    mutate((prev) => [manual, ...prev.filter((m) => m.id !== manual.id)]);
    setUploadOpen(false);
    setToast(tM("uploadToast", { title: manual.title }));
  };


  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header */}
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {tKb("breadcrumbHome")} &gt; {tKb("breadcrumbKb")} &gt; {tM("breadcrumbManuals")}
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            {tKb("pageTitle")}
          </h1>

          {/* Tab Bar */}
          <div className="flex">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const count = tab.count ?? "—";
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`px-5 py-3 text-sm ${
                    isActive
                      ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                      : "font-medium text-[var(--text-secondary)]"
                  }`}
                >
                  {tab.label} ({count})
                </Link>
              );
            })}
          </div>
        </div>

        {/* Filter row */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          <select
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)]"
            aria-label={tM("brandFilterLabel")}
          >
            <option value="">{tM("allBrands")}</option>
            {BRAND_OPTIONS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          {brand && (
            <button
              onClick={() => setBrand("")}
              className="h-10 rounded-lg px-3 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            >
              {tM("clearFilter")}
            </button>
          )}
        </div>

        {/* Body */}
        <div className="flex flex-1 flex-col gap-6 overflow-auto pl-14 pr-4 py-6 md:px-8">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Upload Dropzone */}
          <button
            onClick={() => setUploadOpen(true)}
            className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-[var(--border)] bg-[var(--bg-page)] px-10 py-10 transition hover:border-[var(--primary)] hover:bg-white"
          >
            <CloudUpload className="h-12 w-12 text-[var(--primary)]" />
            <div className="flex items-center gap-1">
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                {tM("uploadCta")}
              </span>
            </div>
            <span className="text-xs text-[var(--text-disabled)]">
              {tM("uploadHint")}
            </span>
          </button>

          {/* File Table */}
          <ManualsTable
            items={items}
            loading={loading}
            onDelete={(m) => {
              setDeleteError(null);
              setConfirmTarget(m);
            }}
            pendingDeleteId={deletingId}
          />

          {/* Load more / total */}
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-secondary)]">
              {loading
                ? tM("loading")
                : `${tM("showCount", { count: items.length })}${hasMore ? tM("hasMoreSuffix") : ""}`}
            </span>
            {hasMore && !loading && (
              <button
                onClick={loadMore}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
              >
                {tM("loadMore")}
              </button>
            )}
          </div>
        </div>
      </div>

      {confirmTarget && (
        <ConfirmDeleteModal
          manual={confirmTarget}
          pending={deletingId === confirmTarget.id}
          error={deleteError}
          onCancel={() => {
            if (deletingId) return;
            setConfirmTarget(null);
            setDeleteError(null);
          }}
          onConfirm={() => handleDelete(confirmTarget)}
        />
      )}

      {uploadOpen && (
        <UploadManualModal
          brandOptions={BRAND_OPTIONS}
          onCancel={() => setUploadOpen(false)}
          onUploaded={handleUploaded}
        />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}

function ConfirmDeleteModal({
  manual,
  pending,
  error,
  onCancel,
  onConfirm,
}: {
  manual: Manual;
  pending: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const t = useTranslations("kb.manuals.deleteModal");
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={() => !pending && onCancel()}
    >
      <div
        className="w-full max-w-[460px] rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2">
          <Trash2 className="h-5 w-5 text-[var(--status-danger)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>
        <p className="text-[13px] leading-[1.6] text-[var(--text-secondary)]">
          {t("confirmPrefix")}
          <span className="px-1 font-semibold text-[var(--text-primary)]">
            {t("confirmTitle", { title: manual.title })}
          </span>
          {t("confirmSuffix")}
        </p>

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={onConfirm}
            disabled={pending}
            className="rounded-md bg-[var(--status-danger)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("deleting") : t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

function UploadManualModal({
  brandOptions,
  onCancel,
  onUploaded,
}: {
  brandOptions: string[];
  onCancel: () => void;
  onUploaded: (manual: Manual) => void;
}) {
  const t = useTranslations("kb.manuals.uploadModal");
  const [file, setFile] = useState<File | null>(null);
  const [brand, setBrand] = useState<string>(brandOptions[0] ?? "");
  const [model, setModel] = useState<string>("");
  const [title, setTitle] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const fileInvalid =
    file != null &&
    (file.size > MAX_UPLOAD_BYTES ||
      !file.name.toLowerCase().endsWith(ACCEPTED_EXTENSION));
  const valid =
    !!file &&
    !fileInvalid &&
    brand.trim().length > 0 &&
    title.trim().length > 0 &&
    title.trim().length <= 200 &&
    !pending;

  const handleSelectFile = (f: File | null) => {
    setError(null);
    setFile(f);
    if (f && !title.trim()) {
      const auto = f.name.replace(/\.[^.]+$/, "");
      setTitle(auto.slice(0, 200));
    }
  };

  const handleSubmit = async () => {
    if (!file) return;
    setPending(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("brand", brand.trim());
      fd.append("title", title.trim());
      if (model.trim()) fd.append("model", model.trim());
      const res = await api.upload<ManualEnvelope>(
        "/api/v1/knowledge-base/manuals/upload",
        fd,
      );
      if (res.data) onUploaded(res.data);
      else setError(t("noResponse"));
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={() => !pending && onCancel()}
    >
      <div
        className="w-full max-w-[520px] rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CloudUpload className="h-5 w-5 text-[var(--primary)]" />
            <span className="text-[18px] font-semibold text-[var(--text-primary)]">
              {t("title")}
            </span>
          </div>
          <button
            onClick={() => !pending && onCancel()}
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-col gap-4">
          {/* File */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("fileLabel")}
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSION}
              onChange={(e) => handleSelectFile(e.target.files?.[0] ?? null)}
              disabled={pending}
              className="block w-full text-[13px] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--primary)] file:px-3 file:py-2 file:text-white file:hover:opacity-90"
            />
            {file && (
              <span
                className={`text-[11px] ${
                  fileInvalid ? "text-[var(--error)]" : "text-[var(--text-disabled)]"
                }`}
              >
                {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB
                {fileInvalid && t("fileInvalid")}
              </span>
            )}
          </div>

          {/* Brand */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("brandLabel")}
            </label>
            <select
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              disabled={pending}
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-50"
            >
              {brandOptions.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>

          {/* Model */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("modelLabel")}
            </label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value.slice(0, 100))}
              disabled={pending}
              placeholder={t("modelPlaceholder")}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-50"
            />
          </div>

          {/* Title */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("titleLabel")}
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value.slice(0, 200))}
              disabled={pending}
              placeholder={t("titlePlaceholder")}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-50"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {title.trim().length} / 200
            </span>
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              {error}
            </div>
          )}

          <p className="rounded-md bg-[#F0F9FF] px-3 py-2 text-[12px] leading-[1.6] text-[#0C4A6E]">
            {t("info")}
          </p>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("back")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!valid}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("uploading") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
