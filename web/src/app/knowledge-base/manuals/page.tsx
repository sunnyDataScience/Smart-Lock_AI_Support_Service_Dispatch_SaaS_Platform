"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CloudUpload, Trash2 } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ManualsTable from "@/components/knowledge-base/ManualsTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Manual = components["schemas"]["Manual"];
type ManualPage = components["schemas"]["ManualPage"];

const PAGE_SIZE = 20;

const tabs = [
  { label: "案例庫", href: "/knowledge-base/cases", count: 128 },
  { label: "產品手冊", href: "/knowledge-base/manuals", dynamic: true },
  { label: "SOP 草稿", href: "/knowledge-base/sop-drafts", count: 7 },
];

const BRAND_OPTIONS = ["Yale", "Chatlock", "美樂", "Dormakaba", "Philips", "Kaadas"];

export default function ManualsPage() {
  const pathname = usePathname();
  const [items, setItems] = useState<Manual[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [brand, setBrand] = useState<string>("");
  const [confirmTarget, setConfirmTarget] = useState<Manual | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const handleDelete = async (manual: Manual) => {
    setDeletingId(manual.id);
    setDeleteError(null);
    try {
      await api.delete(`/api/v1/knowledge-base/manuals/${encodeURIComponent(manual.id)}`);
      setItems((prev) => prev.filter((m) => m.id !== manual.id));
      setConfirmTarget(null);
      setToast(`已刪除「${manual.title}」`);
    } catch (e) {
      setDeleteError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setDeletingId(null);
    }
  };

  const fetchPage = useCallback(
    async (afterCursor: string | null, append: boolean, brandFilter: string) => {
      setLoading(true);
      setError(null);
      try {
        const query: Record<string, string | number> = { limit: PAGE_SIZE };
        if (afterCursor) query.cursor = afterCursor;
        if (brandFilter) query.brand = brandFilter;
        const res = await api.get<ManualPage>(
          "/api/v1/knowledge-base/manuals",
          { query },
        );
        const newItems = res.items ?? [];
        setItems((prev) => (append ? [...prev, ...newItems] : newItems));
        setCursor(res.next_cursor ?? null);
        setHasMore(!!res.has_more);
      } catch (e) {
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    fetchPage(null, false, brand);
  }, [fetchPage, brand]);

  const showCount = hasMore ? `${items.length}+` : items.length;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header */}
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 知識庫 &gt; 產品手冊
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            知識庫管理
          </h1>

          {/* Tab Bar */}
          <div className="flex">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const count = tab.dynamic ? showCount : tab.count;
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
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <select
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)]"
            aria-label="品牌篩選"
          >
            <option value="">全部品牌</option>
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
              清除篩選
            </button>
          )}
        </div>

        {/* Body */}
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Upload Dropzone (disabled — pending backend pipeline) */}
          <div
            className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-[var(--border)] bg-[var(--bg-page)] px-10 py-10 opacity-60"
            title="即將推出"
          >
            <CloudUpload className="h-12 w-12 text-[var(--text-secondary)]" />
            <div className="flex items-center gap-1">
              <span className="text-sm text-[var(--text-secondary)]">
                上傳功能即將推出（PDF 解析 pipeline 接入後啟用）
              </span>
            </div>
            <span className="text-xs text-[var(--text-disabled)]">
              支援格式：PDF，單檔上限 50MB
            </span>
          </div>

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
                ? "載入中…"
                : `顯示 ${items.length} 筆${hasMore ? "（尚有更多）" : ""}`}
            </span>
            {hasMore && !loading && (
              <button
                onClick={() => fetchPage(cursor, true, brand)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
              >
                載入更多
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
            刪除手冊
          </span>
        </div>
        <p className="text-[13px] leading-[1.6] text-[var(--text-secondary)]">
          確認刪除手冊
          <span className="px-1 font-semibold text-[var(--text-primary)]">
            「{manual.title}」
          </span>
          ？此操作將連同已切片內容（chunks）一併移除，無法復原。
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
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={pending}
            className="rounded-md bg-[var(--status-danger)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "刪除中…" : "確認刪除"}
          </button>
        </div>
      </div>
    </div>
  );
}
