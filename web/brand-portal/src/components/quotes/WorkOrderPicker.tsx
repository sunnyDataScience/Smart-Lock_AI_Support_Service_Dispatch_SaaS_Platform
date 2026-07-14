"use client";

import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { api, tenantPath } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];

// 工單狀態中文標籤（v2 七態；原本下拉每列 {wo.status} 直出英文原始碼）
const WO_STATUS_LABEL: Record<string, string> = {
  created: "已建立",
  assigned: "已派工",
  accepted: "已接單",
  in_progress: "服務中",
  completed: "已完工",
  confirmed: "客戶已確認",
  cancelled: "已取消",
};

interface Props {
  /** 已選工單 UUID（受控）；空字串代表未選 */
  value: string;
  onChange: (workOrderId: string) => void;
}

/** 工單可讀標籤：公單號（TP-000001）+ 客戶名，反查不到才退回短 UUID。 */
function labelOf(wo: WorkOrder): string {
  const no = wo.document_number ?? wo.id.slice(0, 8);
  return wo.customer_name ? `${no}　${wo.customer_name}` : no;
}

/**
 * 工單選擇器 —— 用公單號（TP-000001）或客戶名搜尋工單，免手貼內部 UUID。
 *
 * 受控元件：對外 value 仍是工單 UUID（建報價端點不變），對內把 UUID 反查成
 * 可讀公單號顯示。深連結 ?wo={uuid} 帶入 value 時也會反查公單號，不露 UUID。
 */
export default function WorkOrderPicker({ value, onChange }: Props) {
  const t = useTranslations("admin.quotes");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<WorkOrder[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // value（工單 UUID）變化時反查公單號顯示（深連結 ?wo= 也走這條，避免畫面露 UUID）
  useEffect(() => {
    if (!value) {
      setSelectedLabel(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ data: WorkOrder }>(tenantPath(`/work-orders/${value}`));
        if (!cancelled) setSelectedLabel(labelOf(res.data));
      } catch {
        if (!cancelled) setSelectedLabel(null); // 反查失敗不阻斷，僅不顯示可讀標籤
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [value]);

  // 搜尋（debounce 300ms）：公單號 / 客戶名 / 地址 / 電話皆可（後端 keyword 已含 document_number）
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const h = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.get<{ items: WorkOrder[] }>(
          `${tenantPath("/work-orders")}?keyword=${encodeURIComponent(query.trim())}&limit=20`,
        );
        setResults(res.items ?? []);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(h);
  }, [query]);

  // 點元件外關閉下拉
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function select(wo: WorkOrder) {
    onChange(wo.id);
    setSelectedLabel(labelOf(wo));
    setQuery("");
    setResults([]);
    setOpen(false);
  }

  function clear() {
    onChange("");
    setSelectedLabel(null);
    setQuery("");
  }

  // 已選工單：顯示公單號膠囊（可清除重選）
  if (value && selectedLabel) {
    return (
      <span className="inline-flex items-center gap-2 rounded border border-[var(--primary)] bg-[var(--primary-light)] px-3 py-2 text-sm">
        <span className="font-mono font-semibold text-[var(--primary)]">{selectedLabel}</span>
        <button
          onClick={clear}
          className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          aria-label={t("woPickerClear")}
        >
          <X className="h-4 w-4" />
        </button>
      </span>
    );
  }

  return (
    <div ref={boxRef} className="relative">
      <div className="flex items-center gap-2 rounded border border-[var(--border)] bg-white px-3 py-2">
        <Search className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={t("woPickerPlaceholder")}
          className="w-72 bg-transparent text-sm outline-none"
        />
      </div>
      {open && (query.trim() || loading) && (
        <div className="absolute z-10 mt-1 max-h-72 w-80 overflow-auto rounded border border-[var(--border)] bg-[var(--bg-surface)] shadow-lg">
          {loading && (
            <div className="px-3 py-2 text-sm text-[var(--text-secondary)]">{t("woPickerSearching")}</div>
          )}
          {!loading && results.length === 0 && (
            <div className="px-3 py-2 text-sm text-[var(--text-secondary)]">{t("woPickerNoResult")}</div>
          )}
          {!loading &&
            results.map((wo) => (
              <button
                key={wo.id}
                onClick={() => select(wo)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--bg-page)]"
              >
                <span className="shrink-0 font-mono font-semibold text-[var(--text-primary)]">
                  {wo.document_number ?? wo.id.slice(0, 8)}
                </span>
                <span className="flex-1 truncate text-[var(--text-secondary)]">{wo.customer_name ?? "—"}</span>
                <span className="shrink-0 rounded bg-[var(--bg-page)] px-2 py-[1px] text-xs text-[var(--text-secondary)]">
                  {WO_STATUS_LABEL[wo.status] ?? wo.status}
                </span>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
