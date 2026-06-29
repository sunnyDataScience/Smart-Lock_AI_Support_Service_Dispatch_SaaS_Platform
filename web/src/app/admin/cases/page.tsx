"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Inbox, PhoneCall, Check, AlertTriangle, ListFilter } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, tenantPath } from "@/lib/api";
import { cacheInvalidate } from "@/lib/cache";

interface IntakeCase {
  id: string;
  case_number: string;
  source_channel: string;
  customer_name: string | null;
  customer_phone: string | null;
  summary: string | null;
  status: string;
  first_response_due_at: string | null;
  first_responded_at: string | null;
  sla_overdue?: boolean;
  created_at: string | null;
}

// CR-0108 D1：客服可代建的渠道（LINE 由 agent 自動建案，不在手動表單）
const CHANNEL_OPTIONS: { value: string; label: string }[] = [
  { value: "phone", label: "電話" },
  { value: "web", label: "官網表單" },
  { value: "referral", label: "熟客介紹" },
];
const CHANNEL_LABEL: Record<string, string> = {
  line: "LINE",
  phone: "電話",
  web: "官網表單",
  referral: "熟客介紹",
};
const STATUS_LABEL: Record<string, string> = {
  open: "待回應",
  in_progress: "處理中",
  closed: "已結案",
};

// 狀態徽章配色（待回應=琥珀提醒 / 處理中=藍進行 / 已結案=灰淡出）
const STATUS_STYLE: Record<string, string> = {
  open: "border border-amber-200 bg-amber-50 text-amber-700",
  in_progress: "border border-blue-200 bg-blue-50 text-blue-700",
  closed: "border border-gray-200 bg-gray-100 text-gray-500",
};

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "全部狀態" },
  { value: "open", label: "待回應" },
  { value: "in_progress", label: "處理中" },
  { value: "closed", label: "已結案" },
];

const CHANNEL_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "全部渠道" },
  { value: "line", label: "LINE" },
  { value: "phone", label: "電話" },
  { value: "web", label: "官網表單" },
  { value: "referral", label: "熟客介紹" },
];

// 分鐘數 → 「X 天 / X 小時 Y 分 / Y 分」
function fmtDuration(mins: number): string {
  if (mins >= 1440) return `${Math.floor(mins / 1440)} 天`;
  if (mins >= 60) return `${Math.floor(mins / 60)} 小時 ${mins % 60} 分`;
  return `${mins} 分`;
}

// 首次回應 SLA 顯示：顏色 + 剩餘/逾時時間（綠=充裕、琥珀=即將到期、紅=逾時）
function slaInfo(c: IntakeCase): { label: string; cls: string } {
  if (c.status === "closed") return { label: "—", cls: "text-[var(--text-disabled)]" };
  if (c.first_responded_at) return { label: "已回應", cls: "text-[#15803D]" };
  if (!c.first_response_due_at) return { label: "待回應", cls: "text-[#B45309]" };
  const diffMin = Math.round((new Date(c.first_response_due_at).getTime() - Date.now()) / 60000);
  if (diffMin < 0) return { label: `逾時 ${fmtDuration(-diffMin)}`, cls: "font-semibold text-red-600" };
  if (diffMin <= 30) return { label: `剩 ${fmtDuration(diffMin)}`, cls: "font-semibold text-[#B45309]" };
  return { label: `剩 ${fmtDuration(diffMin)}`, cls: "text-[#15803D]" };
}

export default function IntakeCasesPage() {
  const [items, setItems] = useState<IntakeCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<string | null>(null);

  const [channel, setChannel] = useState("phone");
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [summary, setSummary] = useState("");

  // 列表篩選（client 端，即時不需 re-fetch）
  const [filterStatus, setFilterStatus] = useState("");
  const [filterChannel, setFilterChannel] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ data: IntakeCase[] }>(tenantPath("/cases?limit=200"));
      setItems(res.data ?? []);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.errorCode} (${e.status})：${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create() {
    if (!summary.trim() && !customerName.trim() && !customerPhone.trim()) {
      setError("請至少填寫需求摘要或客戶聯絡資訊");
      return;
    }
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const res = await api.post<{ data: IntakeCase }>(tenantPath("/cases"), {
        source_channel: channel,
        summary: summary.trim() || null,
        customer_name: customerName.trim() || null,
        customer_phone: customerPhone.trim() || null,
      });
      cacheInvalidate("GET:"); // cache key 含完整 URL，用廣域 prefix 清 30s GET 快取
      setOk(`已建立進線案件 ${res.data.case_number}（${CHANNEL_LABEL[channel] ?? channel}）`);
      setCustomerName("");
      setCustomerPhone("");
      setSummary("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.errorCode} (${e.status})：${e.message}` : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(id: string, status: string) {
    setError(null);
    // 樂觀更新：立即反映狀態（含 open→in_progress 補記首次回應），免等網路往返
    setItems((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              status,
              first_responded_at:
                status === "in_progress" && !c.first_responded_at
                  ? new Date().toISOString()
                  : c.first_responded_at,
            }
          : c,
      ),
    );
    try {
      await api.patch(tenantPath(`/cases/${id}`), { status });
      cacheInvalidate("GET:"); // cache key 含完整 URL，用廣域 prefix 清 30s GET 快取
    } catch (e) {
      setError(e instanceof ApiError ? `${e.errorCode} (${e.status})：${e.message}` : String(e));
      await load(); // 失敗時 reload 回滾樂觀更新
    }
  }

  const overdueCount = items.filter((c) => c.sla_overdue).length;
  const hasFilter = filterStatus !== "" || filterChannel !== "" || overdueOnly;
  const visibleItems = useMemo(
    () =>
      items.filter(
        (c) =>
          (!filterStatus || c.status === filterStatus) &&
          (!filterChannel || c.source_channel === filterChannel) &&
          (!overdueOnly || c.sla_overdue),
      ),
    [items, filterStatus, filterChannel, overdueOnly],
  );

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <Inbox className="h-7 w-7 text-[var(--primary)]" />
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">進線案件（Case）</h1>
          <span className="text-[13px] text-[var(--text-secondary)]">
            共 {items.length} 件{hasFilter && `，篩出 ${visibleItems.length} 件`}
          </span>
          {overdueCount > 0 && (
            <span className="ml-1 flex items-center gap-1 rounded bg-red-50 px-2 py-[2px] text-[12px] font-semibold text-red-700">
              <AlertTriangle className="h-3.5 w-3.5" /> {overdueCount} 件 SLA 逾時
            </span>
          )}
        </div>

        <div className="flex-1 overflow-auto pl-14 pr-4 md:px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
          {ok && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
              <Check className="h-4 w-4" /> {ok}
            </div>
          )}

          {/* 代客建案（非 LINE 進線：電話/官網/熟客介紹） */}
          <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4">
            <div className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-[var(--text-primary)]">
              <PhoneCall className="h-5 w-5 text-[var(--primary)]" /> 代客建案（電話/官網/熟客介紹）
            </div>
            <p className="mb-3 text-[12px] text-[var(--text-secondary)]">
              LINE 進線由系統自動建案；此處供客服登記非 LINE 進線。建立後自動發案號並啟動首次回應 SLA 計時。
            </p>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
              <Field label="進線渠道" required>
                <select value={channel} onChange={(e) => setChannel(e.target.value)} className={INPUT}>
                  {CHANNEL_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="客戶姓名">
                <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} className={INPUT} />
              </Field>
              <Field label="客戶電話">
                <input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} className={INPUT} />
              </Field>
              <Field label="需求摘要">
                <input
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="如：三樓鐵門鎖舌卡住"
                  className={INPUT}
                />
              </Field>
            </div>
            <div className="mt-3">
              <button
                onClick={create}
                disabled={busy}
                className="h-[38px] rounded-md bg-[var(--primary)] px-5 text-sm font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
              >
                {busy ? "建立中…" : "建立進線案件"}
              </button>
            </div>
          </div>

          {/* 篩選 + 案件列表 */}
          {loading ? (
            <p className="text-sm text-[var(--text-secondary)]">載入中…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-[var(--text-disabled)]">目前沒有進線案件</p>
          ) : (
            <>
              {/* 篩選列 */}
              <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
                <span className="flex items-center gap-1.5 text-[13px] font-medium text-[var(--text-secondary)]">
                  <ListFilter className="h-4 w-4" /> 篩選
                </span>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className={FILTER_INPUT}
                >
                  {STATUS_FILTERS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <select
                  value={filterChannel}
                  onChange={(e) => setFilterChannel(e.target.value)}
                  className={FILTER_INPUT}
                >
                  {CHANNEL_FILTERS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <label className="flex cursor-pointer items-center gap-1.5 text-[13px] text-[var(--text-primary)]">
                  <input
                    type="checkbox"
                    checked={overdueOnly}
                    onChange={(e) => setOverdueOnly(e.target.checked)}
                    className="h-3.5 w-3.5 accent-red-600"
                  />
                  只看 SLA 逾時
                </label>
                {hasFilter && (
                  <button
                    onClick={() => {
                      setFilterStatus("");
                      setFilterChannel("");
                      setOverdueOnly(false);
                    }}
                    className="ml-auto text-[12px] text-[var(--primary)] hover:underline"
                  >
                    清除篩選
                  </button>
                )}
              </div>

              {/* 表格 */}
              <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] text-xs text-[var(--text-secondary)]">
                    <tr>
                      <th className="px-4 py-3 text-left">案號</th>
                      <th className="px-4 py-3 text-left">渠道</th>
                      <th className="px-4 py-3 text-left">客戶</th>
                      <th className="px-4 py-3 text-left">摘要</th>
                      <th className="px-4 py-3 text-left">狀態</th>
                      <th className="px-4 py-3 text-left">SLA（首次回應）</th>
                      <th className="px-4 py-3 text-left">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleItems.length === 0 ? (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-4 py-8 text-center text-[13px] text-[var(--text-disabled)]"
                        >
                          沒有符合篩選條件的案件
                        </td>
                      </tr>
                    ) : (
                      visibleItems.map((c) => {
                        const sla = slaInfo(c);
                        return (
                          <tr key={c.id} className="border-t border-[var(--border)]">
                            <td className="px-4 py-3 font-mono text-[13px] font-medium text-[var(--text-primary)]">
                              {c.case_number}
                            </td>
                            <td className="px-4 py-3 text-[var(--text-secondary)]">
                              {CHANNEL_LABEL[c.source_channel] ?? c.source_channel}
                            </td>
                            <td className="px-4 py-3 text-[var(--text-secondary)]">
                              {c.customer_name || "—"}
                              {c.customer_phone ? (
                                <span className="text-[var(--text-disabled)]"> · {c.customer_phone}</span>
                              ) : null}
                            </td>
                            <td className="px-4 py-3 text-[var(--text-secondary)]">{c.summary || "—"}</td>
                            <td className="px-4 py-3">
                              <span
                                className={`rounded px-2 py-[2px] text-[12px] ${
                                  STATUS_STYLE[c.status] ?? "border border-gray-200 bg-gray-100 text-gray-500"
                                }`}
                              >
                                {STATUS_LABEL[c.status] ?? c.status}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`text-[12px] ${sla.cls}`}>{sla.label}</span>
                            </td>
                            <td className="px-4 py-3">
                              {c.status === "open" && (
                                <button
                                  onClick={() => updateStatus(c.id, "in_progress")}
                                  className="rounded border border-[var(--border)] px-2 py-1 text-[12px] text-[var(--text-primary)] hover:bg-[#F1F5F9]"
                                >
                                  標記處理中
                                </button>
                              )}
                              {c.status === "in_progress" && (
                                <button
                                  onClick={() => updateStatus(c.id, "closed")}
                                  className="rounded border border-[var(--border)] px-2 py-1 text-[12px] text-[var(--text-primary)] hover:bg-[#F1F5F9]"
                                >
                                  結案
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const INPUT =
  "w-full rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none";

const FILTER_INPUT =
  "rounded-md border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)] focus:border-[var(--primary)] focus:outline-none";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      {children}
    </label>
  );
}
