"use client";

/**
 * RestockInventoryModal — FR-0007 補貨 modal (POST :restock)
 *
 * 對應 backend: POST /tenants/{tid}/inventory/items/{itemId}:restock
 *   body: { quantity: int>0, supplier?: str, notes?: str }
 *   operation_id: restockInventoryV2
 */

import { useState } from "react";
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

export interface RestockInventoryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  itemId: string | null;
  itemName: string;
  currentQuantity: number;
  onSuccess?: () => void;
}

export default function RestockInventoryModal({
  open,
  onOpenChange,
  itemId,
  itemName,
  currentQuantity,
  onSuccess,
}: RestockInventoryModalProps) {
  const { toast } = useToast();
  const [quantity, setQuantity] = useState("");
  const [supplier, setSupplier] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setQuantity("");
    setSupplier("");
    setNotes("");
    setError(null);
  }

  async function handleSubmit() {
    if (!itemId) return;
    const qty = parseInt(quantity, 10);
    if (Number.isNaN(qty) || qty <= 0) {
      setError("補貨數量必須為正整數");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.post(tenantPath(`/inventory/items/${itemId}:restock`), {
        quantity: qty,
        supplier: supplier.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      toast({
        variant: "success",
        title: "補貨成功",
        description: `${itemName} +${qty}`,
      });
      reset();
      onOpenChange(false);
      onSuccess?.();
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
      <ModalContent size="sm">
        <ModalHeader>
          <ModalTitle>補貨入庫</ModalTitle>
          <ModalDescription>
            {itemName}（目前庫存：{currentQuantity}）
          </ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              補貨數量 <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="例：50"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              disabled={submitting}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              供應商
            </label>
            <input
              type="text"
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              placeholder="（選填）"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              disabled={submitting}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              備註
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="（選填）採購單號、批次號等"
              rows={3}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              disabled={submitting}
            />
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <ModalFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !quantity}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "送出中…" : "確認補貨"}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
