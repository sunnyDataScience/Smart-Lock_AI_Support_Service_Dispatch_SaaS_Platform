"use client";

import { Upload } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

// ── 師傅證件上傳共用元件（CR-0115 §8-2a 兩階段上傳）─────────────────────────
// 兩個消費端共用（抽出避免複製貼上兩份）：
//   1. /tech-register 註冊成功後的內嵌上傳步驟
//   2. /upload-docs/[token] 補件獨立頁（W3-6 免 email 自助方案：
//      平台 admin 簽發補件 token → 師傅憑連結公開上傳）
// 皆憑一次性 token 打公開端點 POST /api/v1/technicians/registration-documents；
// token 無效/過期/超額 → 後端回 403 UPLOAD_TOKEN_INVALID（單一錯誤碼防探測）。

/** 證件槽位（type 對齊後端 doc_type 白名單；label 走 i18n slots.*） */
export const DOC_SLOT_TYPES = ["id_front", "id_back", "license", "insurance"] as const;

const MAX_FILE_BYTES = 10 * 1024 * 1024;

export interface RegistrationDocUploadController {
  /** docType → 已上傳的檔名 */
  uploaded: Record<string, string>;
  uploadedCount: number;
  /** 上傳中的 docType；null = 無進行中上傳 */
  uploading: string | null;
  /** docType → 錯誤訊息（空字串 = 無錯誤） */
  errors: Record<string, string>;
  handleFile: (docType: string, file: File | null) => Promise<void>;
}

/**
 * 上傳狀態與行為 hook —— 頁面層據此渲染自己的標題/底部按鈕，
 * 槽位清單則交給 <DocUploadSlots ctrl={...} />。
 */
export function useRegistrationDocUpload(
  token: string,
  opts?: {
    /** token 無效/過期（403 UPLOAD_TOKEN_INVALID）—— 補件頁據此切換為失效畫面 */
    onTokenInvalid?: () => void;
  },
): RegistrationDocUploadController {
  const t = useTranslations("techPortal.docUpload");
  const [uploaded, setUploaded] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function handleFile(docType: string, file: File | null) {
    if (!file || uploading) return;
    // 客戶端預檢：超過 10MB 直接擋，不整包上傳才拿到泛化錯誤。
    if (file.size > MAX_FILE_BYTES) {
      setErrors((prev) => ({ ...prev, [docType]: t("fileTooLarge") }));
      return;
    }
    setUploading(docType);
    setErrors((prev) => ({ ...prev, [docType]: "" }));
    try {
      const fd = new FormData();
      fd.append("token", token);
      fd.append("doc_type", docType);
      fd.append("file", file);
      await api.upload("/api/v1/technicians/registration-documents", fd);
      setUploaded((prev) => ({ ...prev, [docType]: file.name }));
    } catch (err) {
      setErrors((prev) => ({ ...prev, [docType]: friendlyError(err) }));
      if (err instanceof ApiError && err.errorCode === "UPLOAD_TOKEN_INVALID") {
        opts?.onTokenInvalid?.();
      }
    } finally {
      setUploading(null);
    }
  }

  return {
    uploaded,
    uploadedCount: Object.keys(uploaded).length,
    uploading,
    errors,
    handleFile,
  };
}

/** 證件槽位清單 UI（label / 檔案提示 / 上傳按鈕文案皆 i18n） */
export default function DocUploadSlots({
  ctrl,
}: {
  ctrl: RegistrationDocUploadController;
}) {
  const t = useTranslations("techPortal.docUpload");
  const { uploaded, uploading, errors, handleFile } = ctrl;

  return (
    <div className="flex flex-col gap-2">
      {DOC_SLOT_TYPES.map((type) => (
        <label
          key={type}
          className={`flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-2.5 transition ${
            uploaded[type]
              ? "border-green-300 bg-green-50"
              : "border-[var(--border)] hover:bg-[var(--bg-page)]"
          }`}
        >
          <div className="flex min-w-0 flex-col">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              {t(`slots.${type}`)}
            </span>
            {uploaded[type] ? (
              <span className="truncate text-xs text-green-700">✓ {uploaded[type]}</span>
            ) : (
              <span className="text-xs text-[var(--text-disabled)]">{t("fileHint")}</span>
            )}
            {errors[type] && <span className="text-xs text-red-600">{errors[type]}</span>}
          </div>
          <span className="flex shrink-0 items-center gap-1 rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)]">
            <Upload className="h-3.5 w-3.5" />
            {uploading === type
              ? t("uploadingBtn")
              : uploaded[type]
                ? t("reupload")
                : t("chooseFile")}
          </span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            className="hidden"
            disabled={!!uploading}
            onChange={(e) => {
              handleFile(type, e.target.files?.[0] ?? null);
              e.target.value = ""; // 允許同檔重選
            }}
          />
        </label>
      ))}
    </div>
  );
}
