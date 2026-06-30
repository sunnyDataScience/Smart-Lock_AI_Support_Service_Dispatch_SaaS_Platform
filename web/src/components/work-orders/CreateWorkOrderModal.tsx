"use client";

/**
 * CreateWorkOrderModal — 新增工單 modal
 *
 * 對應 backend: POST createWorkOrderV2
 *   body: { problem_card_id, customer_address?, customer_name?, customer_phone? }
 *
 * Flow：因 backend 限定工單需從已確認 problem_card 衍生，
 * 此 modal 走兩步驟：
 *   1. 選 problem card (search + list)
 *   2. 補 customer 資訊（選填）+ 送出
 */

import { useEffect, useMemo, useState } from "react";
import { Search, RefreshCw, AlertCircle } from "lucide-react";
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardPage = components["schemas"]["ProblemCardPage"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

export interface CreateWorkOrderModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (workOrderId: string) => void;
}

const URGENCY_LABEL: Record<string, string> = {
  low: "低",
  normal: "一般",
  high: "高",
  critical: "緊急",
};

const URGENCY_COLOR: Record<string, string> = {
  low: "#94A3B8",
  normal: "#2563EB",
  high: "#EA580C",
  critical: "#DC2626",
};

export default function CreateWorkOrderModal({
  open,
  onOpenChange,
  onSuccess,
}: CreateWorkOrderModalProps) {
  const { toast } = useToast();
  const [step, setStep] = useState<"pick" | "fill">("pick");
  const [cards, setCards] = useState<ProblemCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);

  const [customerAddress, setCustomerAddress] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCard = useMemo(
    () => cards.find((c) => c.id === selectedCardId) ?? null,
    [cards, selectedCardId],
  );

  async function fetchCards() {
    setLoading(true);
    setError(null);
    try {
      const q: Record<string, string | number> = { limit: 50 };
      if (keyword.trim()) q.keyword = keyword.trim();
      const res = await api.get<ProblemCardPage>(tenantPath("/problem-cards"), {
        query: q,
      });
      setCards(res.items ?? []);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (open && step === "pick") fetchCards();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step]);

  function reset() {
    setStep("pick");
    setSelectedCardId(null);
    setKeyword("");
    setCustomerAddress("");
    setCustomerName("");
    setCustomerPhone("");
    setError(null);
  }

  async function handleSubmit() {
    if (!selectedCardId) {
      setError("請選擇來源問題卡");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, string> = { problem_card_id: selectedCardId };
      if (customerAddress.trim()) body.customer_address = customerAddress.trim();
      if (customerName.trim()) body.customer_name = customerName.trim();
      if (customerPhone.trim()) body.customer_phone = customerPhone.trim();

      const res = await api.post<WorkOrderEnvelope>(
        tenantPath("/work-orders"),
        body,
      );
      const wo = res.data;
      toast({
        variant: "success",
        title: "工單已建立",
        description: wo?.id ? `編號 ${wo.id.slice(0, 8)}` : "請見列表",
      });
      reset();
      onOpenChange(false);
      if (wo?.id) onSuccess?.(wo.id);
    } catch (e) {
      const msg =
        friendlyError(e);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <ModalContent size="lg">
        <ModalHeader>
          <ModalTitle>新增工單</ModalTitle>
          <ModalDescription>
            從已確認問題卡建立工單（backend createWorkOrderV2）
          </ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4">
          <div className="mb-4 flex items-center gap-2 text-[12px]">
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full ${
                step === "pick" ? "bg-blue-600 text-white" : "bg-blue-100 text-blue-600"
              }`}
            >
              1
            </span>
            <span className={step === "pick" ? "font-medium" : "text-gray-500"}>
              選擇問題卡
            </span>
            <span className="mx-1 text-gray-300">›</span>
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full ${
                step === "fill" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-400"
              }`}
            >
              2
            </span>
            <span className={step === "fill" ? "font-medium" : "text-gray-400"}>
              客戶資訊
            </span>
          </div>

          {step === "pick" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="flex h-9 flex-1 items-center gap-2 rounded-md border border-gray-300 bg-white px-3">
                  <Search className="h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") fetchCards();
                    }}
                    placeholder="關鍵字：地址 / 品牌 / 型號"
                    className="flex-1 bg-transparent text-sm outline-none"
                    disabled={loading}
                  />
                </div>
                <button
                  type="button"
                  onClick={fetchCards}
                  disabled={loading}
                  className="flex h-9 items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                  />
                  {loading ? "搜尋中" : "搜尋"}
                </button>
              </div>

              <div className="max-h-[320px] overflow-auto rounded-md border border-gray-200">
                {!loading && cards.length === 0 && (
                  <div className="flex h-[120px] items-center justify-center text-sm text-gray-500">
                    {keyword ? "查無符合問題卡" : "尚無問題卡"}
                  </div>
                )}
                {cards.map((c) => {
                  const sel = c.id === selectedCardId;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => setSelectedCardId(c.id)}
                      className={`flex w-full flex-col gap-1 border-b border-gray-100 px-3 py-2 text-left last:border-b-0 ${
                        sel ? "bg-blue-50" : "hover:bg-gray-50"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[12px] text-gray-700">
                          {c.id.slice(0, 8)}
                        </span>
                        <span
                          className="rounded-[10px] px-2 py-[1px] text-[11px] font-medium text-white"
                          style={{
                            backgroundColor:
                              URGENCY_COLOR[c.urgency] ?? "#94A3B8",
                          }}
                        >
                          {URGENCY_LABEL[c.urgency] ?? c.urgency}
                        </span>
                        <span className="text-[12px] font-medium text-gray-900">
                          {c.brand} {c.model}
                        </span>
                        <span className="ml-auto text-[11px] text-gray-500">
                          {c.status}
                        </span>
                      </div>
                      <span className="text-[12px] text-gray-600 line-clamp-2">
                        {c.symptom}
                      </span>
                    </button>
                  );
                })}
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </div>
          )}

          {step === "fill" && selectedCard && (
            <div className="space-y-4">
              <div className="rounded-md border border-blue-200 bg-blue-50 p-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[12px] text-gray-700">
                    {selectedCard.id.slice(0, 8)}
                  </span>
                  <span className="text-[13px] font-medium text-gray-900">
                    {selectedCard.brand} {selectedCard.model}
                  </span>
                </div>
                <p className="mt-1 text-[12px] text-gray-700">
                  {selectedCard.symptom}
                </p>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  服務地址
                </label>
                <input
                  type="text"
                  value={customerAddress}
                  onChange={(e) => setCustomerAddress(e.target.value)}
                  placeholder="（選填，缺省用客戶 profile）"
                  maxLength={300}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  disabled={submitting}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    聯絡人
                  </label>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="（選填）"
                    maxLength={80}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    disabled={submitting}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    電話
                  </label>
                  <input
                    type="tel"
                    value={customerPhone}
                    onChange={(e) => setCustomerPhone(e.target.value)}
                    placeholder="（選填）"
                    maxLength={30}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    disabled={submitting}
                  />
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </div>
          )}
        </div>

        <ModalFooter>
          {step === "pick" && (
            <>
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => setStep("fill")}
                disabled={!selectedCardId}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                下一步
              </button>
            </>
          )}
          {step === "fill" && (
            <>
              <button
                type="button"
                onClick={() => setStep("pick")}
                disabled={submitting}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                上一步
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || !selectedCardId}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "建立中…" : "建立工單"}
              </button>
            </>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
