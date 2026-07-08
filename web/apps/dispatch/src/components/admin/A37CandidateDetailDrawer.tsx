"use client";

/**
 * A37 Candidate Detail Drawer — 派工人工介入單一候選技師詳情。
 *
 * 對應 backend: GET /tenants/{tid}/dispatch:candidate-detail
 *   ?work_order_id=...&technician_id=...
 * (operation_id: getDispatchCandidateDetailV2)
 *
 * 採用業主 AI 推薦方案（選項 1）：用既有 Drawer 元件 (Radix Dialog) 套，
 * 最低成本與 design system 一致。
 */

import { useEffect, useState } from "react";
import { CheckCircle, XCircle, AlertCircle, Phone, MapPin } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@shared/components/ui/Drawer";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";

interface CandidateDetail {
  technician: {
    id: string;
    name?: string | null;
    phone?: string | null;
    capabilities?: string[];
    regions?: string[];
    rating?: number | null;
    status?: string | null;
  };
  dispatch_context: {
    work_order_id: string;
    wo_brand: string | null;
    wo_district: string | null;
    skill_match: string;
    distance_explain: string;
    rating_explain: string;
    excluded_by_circuit: boolean;
    eta_minutes: number | null;
  };
  workload_heatmap: unknown | null;
}

export interface A37CandidateDetailDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workOrderId: string | null;
  technicianId: string | null;
}

function formatError(e: unknown): string {
  return friendlyError(e);
}

export default function A37CandidateDetailDrawer({
  open,
  onOpenChange,
  workOrderId,
  technicianId,
}: A37CandidateDetailDrawerProps) {
  const [data, setData] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !workOrderId || !technicianId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get<CandidateDetail>(
        tenantPath(
          `/dispatch:candidate-detail?work_order_id=${workOrderId}&technician_id=${technicianId}`,
        ),
      )
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(formatError(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, workOrderId, technicianId]);

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent side="right" size="lg">
        <DrawerHeader>
          <DrawerTitle>候選技師詳情</DrawerTitle>
        </DrawerHeader>

        <div className="px-6 py-4 space-y-4 overflow-y-auto">
          {loading && (
            <div className="text-center py-8 text-sm text-gray-500">載入中…</div>
          )}

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {data && !loading && (
            <>
              {/* 基本資料 */}
              <section>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  技師資料
                </h3>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-1.5 text-sm">
                  <div className="font-semibold text-gray-900 text-base">
                    {data.technician.name ?? "（未命名）"}
                  </div>
                  {data.technician.phone && (
                    <div className="flex items-center gap-1 text-gray-600">
                      <Phone size={12} />
                      {data.technician.phone}
                    </div>
                  )}
                  {data.technician.regions && data.technician.regions.length > 0 && (
                    <div className="flex items-center gap-1 text-gray-600">
                      <MapPin size={12} />
                      {data.technician.regions.join("、")}
                    </div>
                  )}
                  {data.technician.capabilities &&
                    data.technician.capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {data.technician.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="inline-block rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    )}
                  {data.technician.rating !== null &&
                    data.technician.rating !== undefined && (
                      <div className="text-gray-600">
                        評分：
                        <span className="font-semibold text-gray-900">
                          {data.technician.rating.toFixed(1)}
                        </span>{" "}
                        / 5
                      </div>
                    )}
                </div>
              </section>

              {/* 派工脈絡 */}
              <section>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  派工匹配脈絡
                </h3>
                <div className="space-y-2">
                  <ContextRow
                    label="技能匹配"
                    value={data.dispatch_context.skill_match}
                    status={
                      data.dispatch_context.skill_match.includes("完全")
                        ? "good"
                        : "neutral"
                    }
                  />
                  <ContextRow
                    label="距離說明"
                    value={data.dispatch_context.distance_explain}
                    status="neutral"
                  />
                  <ContextRow
                    label="評分說明"
                    value={data.dispatch_context.rating_explain}
                    status="neutral"
                  />
                  <ContextRow
                    label="連續派工保護"
                    value={
                      data.dispatch_context.excluded_by_circuit
                        ? "已觸發 — 此技師不應再派單"
                        : "未觸發"
                    }
                    status={data.dispatch_context.excluded_by_circuit ? "bad" : "good"}
                  />
                  {data.dispatch_context.eta_minutes !== null && (
                    <ContextRow
                      label="預估到場"
                      value={`${data.dispatch_context.eta_minutes} 分鐘`}
                      status="neutral"
                    />
                  )}
                </div>
              </section>

              {/* 工單資訊 */}
              <section>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  工單資訊
                </h3>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm space-y-1">
                  {data.dispatch_context.wo_brand && (
                    <div>
                      <span className="text-gray-500">品牌：</span>
                      <span className="text-gray-900">
                        {data.dispatch_context.wo_brand}
                      </span>
                    </div>
                  )}
                  {data.dispatch_context.wo_district && (
                    <div>
                      <span className="text-gray-500">區域：</span>
                      <span className="text-gray-900">
                        {data.dispatch_context.wo_district}
                      </span>
                    </div>
                  )}
                </div>
              </section>

              {/* 負載熱圖 */}
              {data.workload_heatmap && (
                <section>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    當週負載
                  </h3>
                  <pre className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700 overflow-auto">
                    {JSON.stringify(data.workload_heatmap, null, 2)}
                  </pre>
                </section>
              )}
            </>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}

function ContextRow({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status: "good" | "bad" | "neutral";
}) {
  const Icon =
    status === "good" ? CheckCircle : status === "bad" ? XCircle : AlertCircle;
  const color =
    status === "good"
      ? "text-green-600"
      : status === "bad"
        ? "text-red-600"
        : "text-gray-400";
  return (
    <div className="flex items-start gap-2 text-sm">
      <Icon size={16} className={`mt-0.5 flex-shrink-0 ${color}`} />
      <div>
        <span className="font-medium text-gray-700">{label}：</span>
        <span className="text-gray-900">{value}</span>
      </div>
    </div>
  );
}
