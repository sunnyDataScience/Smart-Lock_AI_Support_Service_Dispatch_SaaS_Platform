"use client";

/**
 * CreateTechnicianModal — FR-0044 新增技師 modal (POST createTechnician)
 *
 * 對應 backend: POST /tenants/{tid}/technicians
 *   body: { display_name, coverage_areas: string[], phone?, email?,
 *           capabilities?: string[] }
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
import { LOCK_BRANDS_HINT } from "@/lib/constants/brands";

export interface CreateTechnicianModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export default function CreateTechnicianModal({
  open,
  onOpenChange,
  onSuccess,
}: CreateTechnicianModalProps) {
  const { toast } = useToast();
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [coverageAreas, setCoverageAreas] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setDisplayName("");
    setPhone("");
    setEmail("");
    setCoverageAreas("");
    setCapabilities("");
    setError(null);
  }

  async function handleSubmit() {
    if (!displayName.trim()) {
      setError("技師姓名為必填");
      return;
    }
    const areas = coverageAreas
      .split(/[,，、]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (areas.length === 0) {
      setError("至少填一個服務區域");
      return;
    }
    const caps = capabilities
      .split(/[,，、]/)
      .map((s) => s.trim())
      .filter(Boolean);

    setSubmitting(true);
    setError(null);
    try {
      await api.post(tenantPath("/technicians"), {
        display_name: displayName.trim(),
        coverage_areas: areas,
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        capabilities: caps.length > 0 ? caps : undefined,
      });
      toast({
        variant: "success",
        title: "新增成功",
        description: `${displayName} 已建立`,
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
          <ModalTitle>新增技師</ModalTitle>
          <ModalDescription>建立 tenant 技師 onboarding（FR-0044）</ModalDescription>
        </ModalHeader>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              技師姓名 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="例：王大鎖"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                電話
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="（選填）"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="（選填）"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                disabled={submitting}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              服務區域 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={coverageAreas}
              onChange={(e) => setCoverageAreas(e.target.value)}
              placeholder="逗號分隔，例：台北市信義區, 大安區"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              disabled={submitting}
            />
            <p className="text-xs text-gray-500 mt-1">逗號（,/，/、）分隔多個區域</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              專長品牌（capabilities）
            </label>
            <input
              type="text"
              value={capabilities}
              onChange={(e) => setCapabilities(e.target.value)}
              placeholder={`（選填）例：${LOCK_BRANDS_HINT}`}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
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
            disabled={submitting || !displayName.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "建立中…" : "建立技師"}
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
