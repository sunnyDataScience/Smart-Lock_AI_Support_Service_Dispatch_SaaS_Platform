"use client";

/**
 * CreateInventoryItemModal — FR-0007 新增物料 modal (POST createInventoryItemV2)
 *
 * 對應 backend: POST /tenants/{tid}/inventory/items
 *   body: { part_number, name, category?, unit_cost?, quantity_on_hand,
 *           reorder_point, supplier?, owner, serial_required }
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

type Owner = "platform" | "brand" | "locksmith";

export interface CreateInventoryItemModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export default function CreateInventoryItemModal({
  open,
  onOpenChange,
  onSuccess,
}: CreateInventoryItemModalProps) {
  const { toast } = useToast();
  const [partNumber, setPartNumber] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [quantityOnHand, setQuantityOnHand] = useState("0");
  const [reorderPoint, setReorderPoint] = useState("10");
  const [supplier, setSupplier] = useState("");
  const [owner, setOwner] = useState<Owner>("platform");
  const [serialRequired, setSerialRequired] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setPartNumber("");
    setName("");
    setCategory("");
    setUnitCost("");
    setQuantityOnHand("0");
    setReorderPoint("10");
    setSupplier("");
    setOwner("platform");
    setSerialRequired(false);
    setError(null);
  }

  async function handleSubmit() {
    if (!partNumber.trim() || !name.trim()) {
      setError("零件編號與品項名稱為必填");
      return;
    }
    const qoh = parseInt(quantityOnHand, 10);
    const rp = parseInt(reorderPoint, 10);
    if (Number.isNaN(qoh) || qoh < 0 || Number.isNaN(rp) || rp < 0) {
      setError("數量需為非負整數");
      return;
    }
    const uc = unitCost ? parseFloat(unitCost) : undefined;
    if (uc !== undefined && (Number.isNaN(uc) || uc < 0)) {
      setError("單價需為非負數");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.post(tenantPath("/inventory/items"), {
        part_number: partNumber.trim(),
        name: name.trim(),
        category: category.trim() || undefined,
        unit_cost: uc,
        quantity_on_hand: qoh,
        reorder_point: rp,
        supplier: supplier.trim() || undefined,
        owner,
        serial_required: serialRequired,
      });
      toast({
        variant: "success",
        title: "新增成功",
        description: `${name}（${partNumber}）已建立`,
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
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>新增物料</ModalTitle>
          <ModalDescription>
            建立 tenant 庫存品項（FR-0007）
          </ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                零件編號 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={partNumber}
                onChange={(e) => setPartNumber(e.target.value)}
                placeholder="例：YDM-4109-001"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                品項名稱 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例：Yale YDM4109 電池"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
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
                placeholder="例：電池"
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
                placeholder="（選填）"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                初始庫存量
              </label>
              <input
                type="number"
                min="0"
                value={quantityOnHand}
                onChange={(e) => setQuantityOnHand(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
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
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              所有者（ADR-0052）
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
              id="serial-required"
              checked={serialRequired}
              onChange={(e) => setSerialRequired(e.target.checked)}
              disabled={submitting}
            />
            <label htmlFor="serial-required" className="text-sm text-gray-700">
              強制序號（ADR-0053：主鎖+高價零件）
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
            disabled={submitting || !partNumber.trim() || !name.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "建立中…" : "建立物料"}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
