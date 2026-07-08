"use client";

/**
 * InventoryLogModal — GET /tenants/{tid}/inventory/transactions?item_id=...
 *
 * 顯示單一 item 的異動 ledger (purchase/consume/return/adjust).
 */

import { useEffect, useState } from "react";
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from "@shared/components/ui/Modal";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";

interface Transaction {
  id: string;
  item_id: string;
  transaction_type: "purchase" | "consume" | "return" | "adjust";
  quantity: number;
  work_order_id: string | null;
  technician_id: string | null;
  serial: string | null;
  notes: string | null;
  created_at: string | null;
}

const TYPE_LABEL: Record<string, { label: string; color: string }> = {
  purchase: { label: "進貨/補貨", color: "text-green-600" },
  consume: { label: "領料", color: "text-orange-600" },
  return: { label: "退料", color: "text-blue-600" },
  adjust: { label: "盤點調整", color: "text-purple-600" },
};

export interface InventoryLogModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  itemId: string | null;
  itemName: string;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("zh-TW", { hour12: false });
}

export default function InventoryLogModal({
  open,
  onOpenChange,
  itemId,
  itemName,
}: InventoryLogModalProps) {
  const [items, setItems] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !itemId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get<{ items: Transaction[] }>(
        tenantPath(`/inventory/transactions?item_id=${itemId}&limit=100`),
      )
      .then((res) => {
        if (!cancelled) setItems(res.items ?? []);
      })
      .catch((e) => {
        if (!cancelled) {
          const msg =
            friendlyError(e);
          setError(msg);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, itemId]);

  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent size="lg">
        <ModalHeader>
          <ModalTitle>異動紀錄</ModalTitle>
          <ModalDescription>{itemName}</ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4 max-h-[60vh] overflow-y-auto">
          {loading && (
            <div className="text-center py-8 text-sm text-gray-500">載入中…</div>
          )}

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="text-center py-8 text-sm text-gray-500">無異動紀錄</div>
          )}

          {items.length > 0 && (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    時間
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    類型
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500">
                    數量
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    備註
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {items.map((t) => {
                  const meta = TYPE_LABEL[t.transaction_type];
                  const sign =
                    t.transaction_type === "consume" ? "-" : "+";
                  return (
                    <tr key={t.id} className="hover:bg-gray-50">
                      <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-500">
                        {formatDateTime(t.created_at)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-sm">
                        <span className={`font-medium ${meta?.color ?? "text-gray-700"}`}>
                          {meta?.label ?? t.transaction_type}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right text-sm font-mono">
                        <span className={meta?.color ?? "text-gray-700"}>
                          {sign}
                          {t.quantity}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-sm text-gray-700">
                        {t.notes ?? <span className="text-gray-400">—</span>}
                        {t.serial && (
                          <div className="text-xs text-gray-400 mt-0.5 font-mono">
                            序號：{t.serial}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <ModalFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            關閉
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
