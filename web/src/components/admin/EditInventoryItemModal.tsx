"use client";

/**
 * EditInventoryItemModal — PATCH /tenants/{tid}/inventory/items/{itemId}
 *
 * 部分更新物料 (name / category / unit_cost / reorder_point / supplier /
 * owner / serial_required)。不動 quantity_on_hand (走 :restock).
 */

import { useEffect, useState } from "react";
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

type InventoryItem = components["schemas"]["InventoryItem"];
type Owner = "platform" | "brand" | "locksmith";

export interface EditInventoryItemModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: InventoryItem | null;
  onSuccess?: () => void;
}

export default function EditInventoryItemModal({
  open,
  onOpenChange,
  item,
  onSuccess,
}: EditInventoryItemModalProps) {
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [reorderPoint, setReorderPoint] = useState("");
  const [supplier, setSupplier] = useState("");
  const [owner, setOwner] = useState<Owner>("platform");
  const [serialRequired, setSerialRequired] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 接 item 設預設值
  useEffect(() => {
    if (item) {
      setName(item.name || "");
      setCategory(item.category || "");
      setUnitCost(item.unit_cost?.toString() || "");
      setReorderPoint(item.reorder_point?.toString() || "");
      setSupplier(item.supplier || "");
      setOwner(((item as any).owner as Owner) || "platform");
      setSerialRequired(!!(item as any).serial_required);
      setError(null);
    }
  }, [item]);

  async function handleSubmit() {
    if (!item) return;
    if (!name.trim()) {
      setError("品項名稱不可空白");
      return;
    }
    const rp = parseInt(reorderPoint, 10);
    if (Number.isNaN(rp) || rp < 0) {
      setError("安全庫存量須為非負整數");
      return;
    }
    const uc = unitCost ? parseFloat(unitCost) : undefined;
    if (uc !== undefined && (Number.isNaN(uc) || uc < 0)) {
      setError("單價須為非負數");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.patch(tenantPath(`/inventory/items/${item.id}`), {
        name: name.trim(),
        category: category.trim() || null,
        unit_cost: uc,
        reorder_point: rp,
        supplier: supplier.trim() || null,
        owner,
        serial_required: serialRequired,
      });
      toast({
        variant: "success",
        title: "更新成功",
        description: `${name} 已更新`,
      });
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
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>編輯物料</ModalTitle>
          <ModalDescription>{item?.part_number}</ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              品項名稱 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                分類
              </label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                單價（NT$）
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={unitCost}
                onChange={(e) => setUnitCost(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                安全庫存量
              </label>
              <input
                type="number"
                min="0"
                value={reorderPoint}
                onChange={(e) => setReorderPoint(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
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
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              所有者
            </label>
            <select
              value={owner}
              onChange={(e) => setOwner(e.target.value as Owner)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            >
              <option value="platform">平台 (platform)</option>
              <option value="brand">品牌商 (brand)</option>
              <option value="locksmith">技師自備 (locksmith)</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="edit-serial-required"
              checked={serialRequired}
              onChange={(e) => setSerialRequired(e.target.checked)}
              disabled={submitting}
            />
            <label htmlFor="edit-serial-required" className="text-sm text-gray-700">
              強制序號
            </label>
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
            disabled={submitting || !name.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "儲存中…" : "儲存變更"}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
