"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Image as ImageIcon, RefreshCw, X, Lock, LockOpen } from "lucide-react";
import { api, auth, getCurrentSession, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

interface MediaItem {
  id: string;
  url: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  purpose: string;
  created_at: string;
  legal_hold?: boolean; // CR-0109 法務保留旗標
}

// CR-0109：可設定法務保留的角色（對齊後端 REVIEW_ROLES）
const LEGAL_HOLD_ROLES = ["admin", "tenant_admin", "super_admin", "operations_manager", "reviewer"];

const PURPOSE_LABEL: Record<string, { label: string; bg: string; color: string }> = {
  door_check_before: { label: "門面前", bg: "#FEF3C7", color: "#92400E" },
  door_check_after: { label: "門面後", bg: "#D1FAE5", color: "#065F46" },
  completion_before: { label: "完工前", bg: "#FEF3C7", color: "#92400E" },
  completion_after: { label: "完工後", bg: "#D1FAE5", color: "#065F46" },
  dispute_evidence_customer: { label: "客戶證據", bg: "#FFEDD5", color: "#9A3412" },
  dispute_evidence_technician: { label: "技師證據", bg: "#DBEAFE", color: "#1E40AF" },
  other: { label: "其他", bg: "#F1F5F9", color: "#475569" },
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

interface ThumbProps {
  item: MediaItem;
  onClick: () => void;
  canManageHold?: boolean;
  onToggleHold?: () => void;
}

/**
 * 縮圖元件：用 fetch + Authorization Bearer 拉資料，產生 blob URL 顯示。
 * 因為 GET /tenants/{tid}/media/{id} 需要 token，img.src 不能直接用 URL。
 * item.url 由後端 v2 response 回傳（已是 tenant-scoped 相對路徑），前端不 hardcode。
 */
function MediaThumb({ item, onClick, canManageHold, onToggleHold }: ThumbProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const ac = new AbortController();
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";
    const token = auth.getAccessToken();
    const tenantId = auth.getTenantId();

    (async () => {
      try {
        const res = await fetch(`${baseUrl}${item.url}`, {
          headers: {
            Authorization: token ? `Bearer ${token}` : "",
            "X-Tenant-ID": tenantId,
          },
          signal: ac.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        if (!cancelled) {
          setBlobUrl(url);
          setLoading(false);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      ac.abort();
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [item.url]);

  const meta = PURPOSE_LABEL[item.purpose] ?? PURPOSE_LABEL.other;
  const isImage = item.content_type.startsWith("image/");

  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative flex h-32 flex-col overflow-hidden rounded-lg border border-[var(--border)] bg-[#F8FAFC] hover:ring-2 hover:ring-[var(--primary)]"
    >
      <span
        className="absolute left-1 top-1 z-10 rounded px-[6px] py-[1px] text-[10px] font-bold"
        style={{ backgroundColor: meta.bg, color: meta.color }}
      >
        {meta.label}
      </span>
      {/* CR-0109：法務保留 🔒 徽章 + 鎖/解 toggle（用 span 避免巢狀 button） */}
      {item.legal_hold && (
        <span
          className="absolute right-1 top-1 z-10 flex items-center gap-[2px] rounded bg-amber-100 px-[5px] py-[1px] text-[9px] font-bold text-amber-800"
          title="法務保留中（不會被自動清除）"
        >
          <Lock className="h-2.5 w-2.5" /> 保留
        </span>
      )}
      {canManageHold && onToggleHold && (
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => { e.stopPropagation(); onToggleHold(); }}
          onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onToggleHold(); } }}
          className="absolute bottom-5 right-1 z-10 flex cursor-pointer items-center gap-[2px] rounded bg-black/55 px-[5px] py-[2px] text-[9px] text-white hover:bg-black/75"
          title={item.legal_hold ? "解除法務保留" : "設定法務保留"}
        >
          {item.legal_hold ? <LockOpen className="h-2.5 w-2.5" /> : <Lock className="h-2.5 w-2.5" />}
          {item.legal_hold ? "解除" : "鎖定"}
        </span>
      )}
      {loading && (
        <div className="flex h-full w-full items-center justify-center text-[11px] text-[var(--text-disabled)]">
          載入中…
        </div>
      )}
      {error && !loading && (
        <div className="flex h-full w-full flex-col items-center justify-center gap-1 px-2 text-center text-[10px] text-red-600">
          <X className="h-4 w-4" />
          載入失敗
        </div>
      )}
      {blobUrl && isImage && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={blobUrl}
          alt={item.filename}
          className="h-full w-full object-cover"
        />
      )}
      {blobUrl && !isImage && (
        <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-[11px] text-[var(--text-secondary)]">
          <ImageIcon className="h-5 w-5" />
          {item.filename.slice(0, 16)}
        </div>
      )}
      <span className="absolute bottom-0 left-0 right-0 bg-black/50 px-1 py-[2px] text-[9px] text-white">
        {formatBytes(item.size_bytes)} · {new Date(item.created_at).toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
      </span>
    </button>
  );
}

interface Props {
  /** 工單模式：load /tenants/{tid}/work-orders/{id}/media */
  workOrderId?: string;
  /** 爭議模式：load /tenants/{tid}/disputes/{id}/media */
  disputeId?: string;
  /** 自動刷新版本號變更時重新拉取（外部上傳成功後 +1）*/
  refreshKey?: number;
  /** 自訂標題（預設「相關媒體」）*/
  title?: string;
}

export default function MediaGallery({
  workOrderId,
  disputeId,
  refreshKey = 0,
  title = "相關媒體",
}: Props) {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewItem, setPreviewItem] = useState<MediaItem | null>(null);

  const fetchPath = workOrderId
    ? tenantPath(`/work-orders/${encodeURIComponent(workOrderId)}/media`)
    : disputeId
      ? tenantPath(`/disputes/${encodeURIComponent(disputeId)}/media`)
      : "";

  const fetchItems = useCallback(async () => {
    if (!fetchPath) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ items: MediaItem[] }>(fetchPath);
      setItems(res.items ?? []);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  }, [fetchPath]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, refreshKey]);

  // CR-0109：法務保留設定（僅工單模式 + 有權角色）
  const role = getCurrentSession()?.role ?? null;
  const canManageHold = !!workOrderId && !!role && LEGAL_HOLD_ROLES.includes(role);

  const toggleHold = useCallback(
    async (item: MediaItem) => {
      try {
        await api.patch(tenantPath(`/media/${encodeURIComponent(item.id)}/legal-hold`), {
          hold: !item.legal_hold,
        });
        setItems((prev) =>
          prev.map((m) => (m.id === item.id ? { ...m, legal_hold: !item.legal_hold } : m)),
        );
      } catch (e) {
        setError(
          friendlyError(e),
        );
      }
    },
    [],
  );

  // 按 purpose 分組
  const grouped = items.reduce<Record<string, MediaItem[]>>((acc, it) => {
    (acc[it.purpose] ??= []).push(it);
    return acc;
  }, {});

  return (
    <section className="rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ImageIcon className="h-4 w-4 text-[var(--text-secondary)]" />
          <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">
            {title}
          </h3>
          <span className="rounded bg-[#F1F5F9] px-2 py-[1px] text-[11px] text-[var(--text-secondary)]">
            {items.length} 張
          </span>
        </div>
        <button
          type="button"
          onClick={fetchItems}
          disabled={loading}
          className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          title="重新整理"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {error && (
        <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {error}
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-[var(--text-disabled)]">
          載入中…
        </div>
      ) : items.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-[var(--text-disabled)]">
          此工單尚無媒體紀錄（門面照片 / 完工照片 / 證據）
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {Object.entries(grouped).map(([purpose, list]) => (
            <div key={purpose}>
              <span className="mb-1 block text-[11px] font-medium text-[var(--text-secondary)]">
                {PURPOSE_LABEL[purpose]?.label ?? purpose}（{list.length}）
              </span>
              <div className="grid grid-cols-3 gap-2 md:grid-cols-4">
                {list.map((item) => (
                  <MediaThumb
                    key={item.id}
                    item={item}
                    onClick={() => setPreviewItem(item)}
                    canManageHold={canManageHold}
                    onToggleHold={() => toggleHold(item)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {previewItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setPreviewItem(null)}
        >
          <button
            type="button"
            onClick={() => setPreviewItem(null)}
            className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
            aria-label="關閉"
          >
            <X className="h-5 w-5" />
          </button>
          <MediaThumb
            item={previewItem}
            onClick={() => {
              /* 不關閉，避免誤觸 */
            }}
          />
        </div>
      )}
    </section>
  );
}
