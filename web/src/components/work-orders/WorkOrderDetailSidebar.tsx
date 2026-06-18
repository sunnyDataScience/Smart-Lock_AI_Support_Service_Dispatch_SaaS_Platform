"use client";

import { useEffect, useState } from "react";
import {
  LockOpen,
  Key,
  Phone,
  MapPin,
  TriangleAlert,
  Clock3,
  Star,
  Info,
} from "lucide-react";
import { ApiError, api, tenantPath } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type Technician = components["schemas"]["Technician"];
type TechnicianEnvelope = components["schemas"]["TechnicianEnvelope"];
type Conversation = components["schemas"]["Conversation"];
type ConversationEnvelope = components["schemas"]["ConversationEnvelope"];

interface Props {
  workOrder?: WorkOrder;
  conversationId?: string;
}

const AVATAR_PALETTE = ["#DBEAFE", "#FEF3C7", "#FCE7F3", "#E0E7FF", "#D1FAE5", "#FEE2E2", "#F3E8FF", "#FFEDD5"];

function avatarColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length];
}

function formatPrice(value?: string | null): string {
  if (!value) return "—";
  const n = parseFloat(value);
  if (Number.isNaN(n)) return "—";
  return `NT$ ${n.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

export default function WorkOrderDetailSidebar({ workOrder, conversationId }: Props) {
  const t = useTranslations("components.workOrders.detailSidebar");

  const brandModel = workOrder
    ? `${workOrder.brand || "—"} ${workOrder.model || ""}`.trim()
    : "—";

  const technicianId = workOrder?.technician_id ?? null;
  const [technician, setTechnician] = useState<Technician | null>(null);
  const [techError, setTechError] = useState<string | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [convError, setConvError] = useState<string | null>(null);

  useEffect(() => {
    if (!technicianId) {
      setTechnician(null);
      setTechError(null);
      return;
    }
    let cancelled = false;
    setTechError(null);
    (async () => {
      try {
        const res = await api.get<TechnicianEnvelope>(
          tenantPath(`/technicians/${encodeURIComponent(technicianId)}`),
        );
        if (!cancelled) setTechnician(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        setTechError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})`
            : e instanceof Error
              ? e.message
              : String(e),
        );
        setTechnician(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [technicianId]);

  useEffect(() => {
    if (!conversationId) {
      setConversation(null);
      setConvError(null);
      return;
    }
    let cancelled = false;
    setConvError(null);
    (async () => {
      try {
        const res = await api.get<ConversationEnvelope>(
          tenantPath(`/conversations/${encodeURIComponent(conversationId)}`),
        );
        if (!cancelled) setConversation(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        setConvError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})`
            : e instanceof Error
              ? e.message
              : String(e),
        );
        setConversation(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  const comingSoon = t("comingSoon");

  return (
    <div className="flex w-[380px] flex-shrink-0 flex-col gap-4 overflow-auto bg-[#F1F5F9] p-5">
      {/* Device Panel — brand/model 真實，其他示意 */}
      <div className="flex flex-col gap-3 rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <div className="flex h-[160px] items-center justify-center rounded-lg bg-[#F8FAFC]">
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-[#E2E8F0]">
            <span className="text-[32px] text-[var(--text-disabled)]">🔒</span>
          </div>
        </div>
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          {brandModel || "—"}
        </span>
        <span className="text-[12px] text-[var(--text-secondary)]">
          {workOrder?.serial_number ? `S/N: ${workOrder.serial_number}` : t("deviceSnLabel")}
        </span>

        <div className="flex gap-2 opacity-70">
          <div className="flex flex-1 flex-col items-center gap-1 rounded-lg bg-[#F8FAFC] p-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full border-[3px] border-[#CBD5E1]">
              <span className="text-[10px] font-semibold text-[var(--text-disabled)]">—</span>
            </div>
            <span className="text-[11px] text-[var(--text-secondary)]">{t("deviceBattery")}</span>
          </div>
          <div className="flex flex-1 flex-col items-center gap-1 rounded-lg bg-[#F8FAFC] p-2">
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded-full bg-[#CBD5E1]" />
              <span className="text-[12px] text-[var(--text-disabled)]">—</span>
            </div>
            <span className="text-[11px] text-[var(--text-secondary)]">{t("deviceConnection")}</span>
          </div>
          <div className="flex flex-1 flex-col items-center gap-1 rounded-lg bg-[#F8FAFC] p-2">
            <Clock3 className="h-5 w-5 text-[#94A3B8]" />
            <span className="text-[12px] text-[var(--text-disabled)]">—</span>
            <span className="text-[11px] text-[var(--text-secondary)]">{t("deviceLastOp")}</span>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <button
            disabled
            title={comingSoon}
            className="flex h-9 items-center justify-center gap-2 rounded-lg bg-[var(--accent)] opacity-60 cursor-not-allowed"
          >
            <LockOpen className="h-4 w-4 text-white" />
            <span className="text-[13px] font-semibold text-white">{t("remoteUnlock")}</span>
          </button>
          <button
            disabled
            title={comingSoon}
            className="flex h-9 items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] opacity-60 cursor-not-allowed"
          >
            <Key className="h-4 w-4 text-[var(--text-primary)]" />
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">{t("resetCode")}</span>
          </button>
        </div>
      </div>

      {/* Quotation — estimated_reward 真實 */}
      <div className="flex flex-col gap-2 rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[16px] font-semibold text-[var(--text-primary)]">
          {t("quotationTitle")}
        </span>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-primary)]">{t("estimateLabel")}</span>
          <span className="font-mono text-[14px] font-semibold text-[var(--text-primary)]">
            {formatPrice(workOrder?.estimated_reward)}
          </span>
        </div>
        <div className="flex items-start gap-2 rounded-md bg-[#F8FAFC] px-3 py-2">
          <Info className="mt-[2px] h-[14px] w-[14px] flex-shrink-0 text-[var(--text-disabled)]" />
          <span className="text-[12px] text-[var(--text-secondary)]">
            {t("quotationInfo")}
          </span>
        </div>
      </div>

      {/* 公單資訊 — CR-0026 標準化欄位（服務類別/保固/完工狀態/狀態原因，真實） */}
      <WorkOrderFieldsPanel workOrder={workOrder} />

      {/* Customer Info — display_name + line_user_id 真實，phone 待 facts 模組 */}
      <CustomerInfoPanel
        conversation={conversation}
        conversationId={conversationId ?? null}
        address={workOrder?.address ?? ""}
        error={convError}
      />

      {/* Technician — 真實 fetch（若 technician_id 存在） */}
      <TechnicianPanel
        technicianId={technicianId}
        technician={technician}
        error={techError}
      />

      {/* Action Panel (disabled) */}
      <div className="flex flex-col gap-2 rounded-lg border-t-2 border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <button
          disabled
          title={comingSoon}
          className="flex h-10 items-center justify-center gap-2 rounded-lg bg-[var(--accent)] opacity-60 cursor-not-allowed"
        >
          <TriangleAlert className="h-4 w-4 text-white" />
          <span className="text-[14px] font-semibold text-white">{t("markIssue")}</span>
        </button>
        <span className="text-center text-[13px] text-[var(--text-secondary)]">
          {t("modulePending")}
        </span>
      </div>
    </div>
  );
}

// CR-0026 enum → 顯示映射（繁中；enum 值由 backend 驗證）
const SERVICE_CATEGORY_LABEL: Record<string, string> = {
  install: "安裝",
  warranty_in: "保內",
  warranty_out: "保外",
  repair: "維修",
};
const WARRANTY_STATUS_LABEL: Record<string, string> = {
  in_warranty: "保固內",
  out_warranty: "保固外",
  not_applicable: "不適用",
};
const COMPLETION_STATUS_LABEL: Record<string, string> = {
  pending_report: "待完工回報",
  pending_photos: "待照片",
  pending_customer_confirm: "待客戶確認",
  pending_cs_review: "待客服審核",
  completed: "已完工",
  closed: "已結案",
};

function WorkOrderFieldsPanel({ workOrder }: { workOrder?: WorkOrder }) {
  const t = useTranslations("components.workOrders.detailSidebar");
  if (!workOrder) return null;

  const rows: { label: string; value: string }[] = [];
  const push = (label: string, value?: string | null) => {
    if (value) rows.push({ label, value });
  };
  push(t("woServiceCategory"), workOrder.service_category
    ? SERVICE_CATEGORY_LABEL[workOrder.service_category] ?? workOrder.service_category
    : null);
  push(t("woProblemType"), workOrder.problem_type);
  push(t("woWarranty"), workOrder.warranty_status
    ? WARRANTY_STATUS_LABEL[workOrder.warranty_status] ?? workOrder.warranty_status
    : null);
  push(t("woDoorType"), workOrder.door_type);
  push(t("woCompletion"), workOrder.completion_status
    ? COMPLETION_STATUS_LABEL[workOrder.completion_status] ?? workOrder.completion_status
    : null);
  push(t("woStatusReason"), workOrder.status_reason);

  return (
    <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
      <span className="text-[16px] font-semibold text-[var(--text-primary)]">
        {t("woFieldsTitle")}
      </span>
      {rows.length === 0 ? (
        <span className="text-[13px] text-[var(--text-disabled)]">{t("woFieldsEmpty")}</span>
      ) : (
        rows.map((r) => (
          <div key={r.label} className="flex items-start justify-between gap-3">
            <span className="text-[13px] text-[var(--text-secondary)]">{r.label}</span>
            <span className="text-[13px] font-medium text-[var(--text-primary)] text-right">
              {r.value}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

function CustomerInfoPanel({
  conversation,
  conversationId,
  address,
  error,
}: {
  conversation: Conversation | null;
  conversationId: string | null;
  address: string;
  error: string | null;
}) {
  const t = useTranslations("components.workOrders.detailSidebar");

  const hasConversation = !!conversationId;
  const linePrefix = conversation?.line_user_id
    ? conversation.line_user_id.slice(0, 12) + "…"
    : null;

  return (
    <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-[16px] font-semibold text-[var(--text-primary)]">
          {t("customerTitle")}
        </span>
        {error && (
          <span className="rounded bg-[#FEE2E2] px-2 py-[2px] text-[11px] text-[#991B1B]">
            {t("loadFailed")}
          </span>
        )}
      </div>

      {!hasConversation ? (
        <span className="text-[13px] text-[var(--text-disabled)]">
          {t("noConversation")}
        </span>
      ) : error ? (
        <span className="text-[12px] text-[var(--text-disabled)]">{error}</span>
      ) : !conversation ? (
        <span className="text-[13px] text-[var(--text-secondary)]">{t("loading")}</span>
      ) : (
        <>
          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
            {conversation.display_name || "—"}
          </span>
          {linePrefix && (
            <div className="flex items-center gap-[6px]">
              <Phone className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              <span
                className="font-mono text-[12px] text-[var(--text-secondary)]"
                title={conversation.line_user_id ?? ""}
              >
                {linePrefix}
              </span>
            </div>
          )}
        </>
      )}

      {address && (
        <div className="flex gap-[6px]">
          <MapPin className="mt-[2px] h-[14px] w-[14px] flex-shrink-0 text-[var(--text-secondary)]" />
          <span className="text-[13px] text-[var(--text-primary)]">
            {address}
          </span>
        </div>
      )}

      {hasConversation && conversation && (
        <a
          href={`/conversations/${conversation.id}`}
          className="text-[12px] font-medium text-[var(--primary)] hover:underline"
        >
          {t("viewConversation")}
        </a>
      )}
    </div>
  );
}

function TechnicianPanel({
  technicianId,
  technician,
  error,
}: {
  technicianId: string | null;
  technician: Technician | null;
  error: string | null;
}) {
  const t = useTranslations("components.workOrders.detailSidebar");

  const ratingFloor = technician ? Math.floor(technician.rating) : 0;

  if (!technicianId) {
    return (
      <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[16px] font-semibold text-[var(--text-primary)]">
          {t("technicianTitle")}
        </span>
        <span className="text-[14px] text-[var(--text-disabled)]">{t("unassigned")}</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-[16px] font-semibold text-[var(--text-primary)]">
            {t("technicianTitle")}
          </span>
          <span className="rounded bg-[#FEE2E2] px-2 py-[2px] text-[11px] text-[#991B1B]">
            {t("loadFailed")}
          </span>
        </div>
        <span className="font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-secondary)]">
          #{technicianId.slice(0, 8)}
        </span>
        <span className="text-[12px] text-[var(--text-disabled)]">{error}</span>
      </div>
    );
  }

  if (!technician) {
    return (
      <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[16px] font-semibold text-[var(--text-primary)]">
          {t("technicianTitle")}
        </span>
        <span className="text-[13px] text-[var(--text-secondary)]">{t("loading")}</span>
      </div>
    );
  }

  const skills = (technician.skills ?? []).slice(0, 5);

  return (
    <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
      <span className="text-[16px] font-semibold text-[var(--text-primary)]">
        {t("technicianTitle")}
      </span>
      <div className="flex items-center gap-[10px]">
        <div
          className="h-10 w-10 flex-shrink-0 rounded-full"
          style={{ backgroundColor: avatarColor(technician.id) }}
        />
        <div className="flex flex-col gap-[2px]">
          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
            {technician.name}
          </span>
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((i) => (
              <Star
                key={i}
                className={
                  i <= ratingFloor
                    ? "h-[14px] w-[14px] fill-[var(--accent)] text-[var(--accent)]"
                    : "h-[14px] w-[14px] text-[#E2E8F0]"
                }
              />
            ))}
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              {technician.rating.toFixed(1)}
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-[6px]">
        <Phone className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
        <span className="font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)]">
          {technician.phone}
        </span>
      </div>
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-[6px]">
          {skills.map((s) => (
            <span
              key={s}
              className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[12px] text-[var(--text-primary)]"
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
