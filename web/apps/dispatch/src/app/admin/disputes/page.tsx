"use client";

import { useEffect, useMemo, useState } from "react";
import { Image as ImageIcon, RefreshCw, FileText, AlertCircle } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import DisputesTable from "@/components/admin/DisputesTable";
import { api, getCurrentSession, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useToast } from "@shared/components/ui/Toast";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";

type Dispute = components["schemas"]["Dispute"];
type DisputePage = components["schemas"]["DisputePage"];
type DisputeStatus = components["schemas"]["DisputeStatus"];
type DisputeType = components["schemas"]["DisputeType"];

type DisputeMediaFile = {
  id: string;
  url: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  purpose: string;
  dispute_id: string | null;
  created_at: string;
};

type DisputeMediaPage = { items?: DisputeMediaFile[]; next_cursor?: string | null };

interface StatusTab {
  value: DisputeStatus | "all";
}

const statusTabs: StatusTab[] = [
  { value: "all" },
  { value: "filed" },
  { value: "in_review" },
  { value: "resolved" },
  { value: "rejected" },
];

const typeBadges: { value: DisputeType; textColor: string; bgColor: string }[] = [
  { value: "pricing", textColor: "#2563EB", bgColor: "#DBEAFE" },
  { value: "quality", textColor: "#7C3AED", bgColor: "#EDE9FE" },
  { value: "warranty", textColor: "#059669", bgColor: "#D1FAE5" },
  { value: "cancellation_fee", textColor: "#EA580C", bgColor: "#FFEDD5" },
  { value: "settlement", textColor: "#DB2777", bgColor: "#FCE7F3" },
];

function formatTwd(amount: string | number | null | undefined): string {
  if (amount == null || amount === "") return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function isImage(contentType: string): boolean {
  return contentType.startsWith("image/");
}

export default function DisputesPage() {
  const t = useTranslations("admin.disputes");
  const tc = useTranslations("admin.common");
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<StatusTab["value"]>("all");
  const [typeFilter, setTypeFilter] = useState<DisputeType | null>(null);
  const [items, setItems] = useState<Dispute[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [media, setMedia] = useState<DisputeMediaFile[]>([]);

  const [resolutionNote, setResolutionNote] = useState("");
  const [resolutionAmount, setResolutionAmount] = useState<string>("");
  const [toMediation, setToMediation] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchDisputes = async (
    status: StatusTab["value"],
    type: DisputeType | null,
  ) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      if (status !== "all") query.status = status;
      if (type) query.dispute_type = type;
      const res = await api.get<DisputePage>(tenantPath("/disputes"), { query });
      const newItems: Dispute[] = res.items ?? [];
      setItems(newItems);
      setSelectedId((prev) =>
        prev && newItems.some((i) => i.id === prev) ? prev : newItems[0]?.id ?? null,
      );
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDisputes(activeTab, typeFilter);
  }, [activeTab, typeFilter]);

  const selected = useMemo(
    () => items.find((i) => i.id === selectedId) ?? null,
    [items, selectedId],
  );

  // load media for selected dispute
  useEffect(() => {
    if (!selectedId) {
      setMedia([]);
      return;
    }
    let alive = true;
    (async () => {
      try {
        const res = await api.get<DisputeMediaPage>(
          tenantPath(`/disputes/${encodeURIComponent(selectedId)}/media`),
        );
        if (alive) setMedia(res.items ?? []);
      } catch {
        if (alive) setMedia([]);
      }
    })();
    return () => {
      alive = false;
    };
  }, [selectedId]);

  // reset form when selection changes
  useEffect(() => {
    setResolutionNote("");
    setResolutionAmount(selected?.resolution_amount ? String(selected.resolution_amount) : "");
    setToMediation(false);
    setFormError(null);
  }, [selectedId, selected?.resolution_amount]);

  const customerEvidence = media.filter((m) => m.purpose === "dispute_evidence_customer");
  const technicianEvidence = media.filter((m) => m.purpose === "dispute_evidence_technician");

  // 決定可下動作
  const selStatus = selected?.status as string | undefined;
  const canReview = selStatus === "filed";
  const canCoSign = selStatus === "in_review" || selStatus === "mediation";
  const canAct = canReview || canCoSign;

  async function handleSubmit() {
    if (!selected) return;
    setFormError(null);

    const note = resolutionNote.trim();
    const amountStr = resolutionAmount.trim();
    const amount = amountStr ? Number(amountStr) : null;
    if (amount != null && !Number.isFinite(amount)) {
      setFormError("金額格式錯誤");
      return;
    }

    if (canCoSign && note.length < 5) {
      setFormError("最終決議至少 5 字");
      return;
    }
    if (canReview && note.length < 1) {
      setFormError("CSM 提案不可為空");
      return;
    }

    // co-sign / review 端點都要求 X-Initiator header（行為人身份,缺則 422）。
    // co-sign 的 SoD：X-Initiator(co-signer) 必須 ≠ reviewed_by,否則 403。
    const initiator = getCurrentSession()?.userId ?? "";
    setSubmitting(true);
    try {
      if (canCoSign) {
        await api.post(
          tenantPath(`/disputes/${encodeURIComponent(selected.id)}:co-sign`),
          { resolution: note, resolution_amount: amount },
          { headers: { "X-Initiator": initiator } },
        );
        toast({
          variant: "success",
          title: "已 co-sign 結案",
          description: `${selected.id.slice(0, 8)} → resolved`,
        });
      } else if (canReview) {
        await api.post(
          tenantPath(`/disputes/${encodeURIComponent(selected.id)}:review`),
          {
            proposed_resolution: note,
            resolution_amount: amount,
            to_mediation: toMediation,
          },
          { headers: { "X-Initiator": initiator } },
        );
        toast({
          variant: "success",
          title: toMediation ? "已轉調解" : "已送 CSM 提案",
          description: `${selected.id.slice(0, 8)} → ${toMediation ? "mediation" : "in_review"}`,
        });
      }
      await fetchDisputes(activeTab, typeFilter);
    } catch (e) {
      const msg =
        friendlyError(e);
      setFormError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* flex-1 + space-y-5（非 flex flex-col gap-5）：避免子層被 flex-shrink 壓縮、
            內容超高時自然溢出觸發捲動。同 /admin/customers 捲軸失效修法。*/}
        <div className="flex-1 space-y-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-center gap-3">
            <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <button
              onClick={() => fetchDisputes(activeTab, typeFilter)}
              disabled={loading}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title={tc("refresh")}
            >
              <RefreshCw
                className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
              />
            </button>
            <span
              className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
              style={{
                backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
                color: error ? "#B91C1C" : "#15803D",
              }}
            >
              <span
                className="h-[6px] w-[6px] rounded-full"
                style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
              />
              {error ? tc("disconnected") : tc("connected")}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {updatedAt
                ? tc("lastUpdated", { time: updatedAt.toLocaleTimeString("zh-TW", { hour12: false }) })
                : "—"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">·</span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {tc("totalCount", { count: items.length })}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Filter Row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                {t("type.label")}
              </span>
              <div className="flex items-center gap-2">
                {typeBadges.map((badge) => {
                  const active = typeFilter === badge.value;
                  return (
                    <button
                      key={badge.value}
                      type="button"
                      onClick={() =>
                        setTypeFilter(active ? null : badge.value)
                      }
                      className={`rounded-xl px-3 py-1 text-xs font-medium transition ${
                        active ? "ring-2 ring-[var(--primary)] ring-offset-1" : "hover:opacity-80"
                      }`}
                      style={{
                        color: badge.textColor,
                        backgroundColor: badge.bgColor,
                      }}
                    >
                      {t(`type.${badge.value}`)}
                    </button>
                  );
                })}
                {typeFilter && (
                  <button
                    type="button"
                    onClick={() => setTypeFilter(null)}
                    className="ml-1 rounded-xl border border-[var(--border)] bg-white px-2 py-1 text-[11px] text-[var(--text-secondary)] hover:bg-[#F8FAFC]"
                  >
                    清除類型
                  </button>
                )}
              </div>
            </div>

            <div className="flex overflow-hidden rounded-md border border-[var(--border)]">
              {statusTabs.map((tab, idx) => (
                <button
                  key={tab.value}
                  onClick={() => setActiveTab(tab.value)}
                  className={`px-[14px] py-[6px] text-[13px] font-medium ${
                    activeTab === tab.value
                      ? "bg-[var(--primary)] text-white"
                      : "bg-[var(--bg-surface)] text-[var(--text-secondary)]"
                  } ${idx > 0 ? "border-l border-[var(--border)]" : ""}`}
                >
                  {t(`tabs.${tab.value}`)}
                </button>
              ))}
            </div>
          </div>

          {/* Dispute Table */}
          <DisputesTable
            items={items}
            loading={loading}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />

          {/* Selected description */}
          {selected && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
              <div className="mb-2 flex items-center gap-2">
                <span className="font-mono text-[12px] font-medium text-[var(--text-secondary)]">
                  {selected.id.slice(0, 8)}
                </span>
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">{t("description")}</span>
              </div>
              <p className="text-[13px] leading-[1.6] text-[var(--text-primary)]">
                {selected.description}
              </p>
              {selected.resolution && (
                <div className="mt-3 rounded-md bg-[#F8FAFC] p-3 text-[13px] leading-[1.6] text-[var(--text-secondary)]">
                  <span className="font-semibold text-[var(--text-primary)]">{t("resolution")}</span>
                  {selected.resolution}
                  {selected.resolution_amount && (
                    <span className="ml-2 font-medium text-[var(--text-primary)]">
                      （{formatTwd(selected.resolution_amount)}）
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Evidence Panel — 接 listMediaForDisputeV2 */}
          {selected && (
            <div className="flex overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <EvidenceSection
                titleColor="#2563EB"
                title={t("evidence.customer")}
                files={customerEvidence}
              />
              <div className="w-px bg-[var(--border)]" />
              <EvidenceSection
                titleColor="#D97706"
                title={t("evidence.technician")}
                files={technicianEvidence}
              />
            </div>
          )}

          {/* Resolution Form */}
          {selected && (
            <div className="flex flex-col gap-4 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
              <div className="flex items-center justify-between">
                <span className="text-base font-semibold text-[var(--text-primary)]">
                  {t("form.title")}
                </span>
                {canAct ? (
                  <span className="rounded-full bg-[#DBEAFE] px-3 py-1 text-[11px] font-medium text-[#1E40AF]">
                    {canCoSign ? "step-2 Ops Manager co-sign" : "step-1 CSM review"}
                  </span>
                ) : (
                  <span className="rounded-full bg-[#F1F5F9] px-3 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                    {selected.status === "resolved" ? "已結案" : selected.status === "rejected" ? "已駁回" : "不可在此狀態送出"}
                  </span>
                )}
              </div>

              <div className="flex flex-col gap-[6px]">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  {canCoSign ? "最終決議（≥ 5 字）" : "CSM 提案"}
                </span>
                <textarea
                  value={resolutionNote}
                  onChange={(e) => setResolutionNote(e.target.value)}
                  disabled={!canAct || submitting}
                  placeholder={canCoSign ? "說明最終處理方案..." : "說明 CSM 提案..."}
                  className="h-[100px] resize-none rounded-md border border-[var(--border)] bg-white px-3 py-3 text-[13px] outline-none disabled:cursor-not-allowed disabled:bg-[var(--bg-page)] disabled:text-[var(--text-disabled)]"
                />
              </div>

              <div className="flex gap-4">
                <div className="flex flex-1 flex-col gap-[6px]">
                  <span className="text-[13px] font-medium text-[var(--text-primary)]">
                    解決金額（選填）
                  </span>
                  <input
                    type="number"
                    inputMode="decimal"
                    value={resolutionAmount}
                    onChange={(e) => setResolutionAmount(e.target.value)}
                    disabled={!canAct || submitting}
                    placeholder="正值補償客戶；負值記為平台應收"
                    className="h-10 rounded-md border border-[var(--border)] bg-white px-3 text-[13px] outline-none disabled:cursor-not-allowed disabled:bg-[var(--bg-page)] disabled:text-[var(--text-disabled)]"
                  />
                </div>

                {canReview && (
                  <div className="flex flex-1 flex-col gap-[6px]">
                    <span className="text-[13px] font-medium text-[var(--text-primary)]">
                      Review 結果
                    </span>
                    <label className="flex h-10 items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3">
                      <input
                        type="checkbox"
                        checked={toMediation}
                        onChange={(e) => setToMediation(e.target.checked)}
                        disabled={submitting}
                      />
                      <span className="text-[13px] text-[var(--text-primary)]">
                        進入調解（不勾則 in_review）
                      </span>
                    </label>
                  </div>
                )}
              </div>

              {formError && (
                <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!canAct || submitting}
                  className="rounded-md bg-[var(--primary)] px-5 py-[10px] text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {submitting
                    ? "送出中…"
                    : canCoSign
                      ? "Co-Sign 結案"
                      : toMediation
                        ? "送 CSM 提案 + 轉調解"
                        : "送 CSM 提案"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EvidenceSection({
  title,
  titleColor,
  files,
}: {
  title: string;
  titleColor: string;
  files: DisputeMediaFile[];
}) {
  return (
    <div className="flex flex-1 flex-col gap-3 p-5">
      <div className="flex items-center justify-between">
        <span className="text-[15px] font-semibold" style={{ color: titleColor }}>
          {title}
        </span>
        <span className="text-[11px] text-[var(--text-secondary)]">
          {files.length} 個檔案
        </span>
      </div>
      {files.length === 0 ? (
        <div className="flex h-[90px] items-center justify-center rounded-md bg-[#F8FAFC]">
          <span className="text-[12px] text-[var(--text-secondary)]">尚無證據檔案</span>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {files.map((f) => (
            <a
              key={f.id}
              href={f.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col overflow-hidden rounded-md border border-[var(--border)] bg-white hover:bg-[#F8FAFC]"
            >
              <div className="flex h-[90px] items-center justify-center bg-[#F1F5F9]">
                {isImage(f.content_type) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={f.url}
                    alt={f.filename}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <FileText className="h-6 w-6 text-[var(--text-disabled)]" />
                )}
              </div>
              <span className="truncate px-2 py-1 text-[11px] text-[var(--text-primary)]">
                {f.filename}
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
