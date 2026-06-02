"use client";

import { useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Camera,
  CheckCircle2,
  Image as ImageIcon,
  X,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";

interface UploadedPhoto {
  section: "before" | "after";
  id: string;
  url: string;
  filename: string;
}

/** 縮圖元件：用 fetch + blob URL 處理 Bearer Token 認證下載 */
function PhotoThumb({
  photo,
  onRemove,
}: {
  photo: UploadedPhoto;
  onRemove: () => void;
}) {
  const tCommon = useTranslations("techPortal.common");
  return (
    <div className="relative h-20 overflow-hidden rounded-md border border-[var(--border)]">
      <span className="flex h-full w-full items-center justify-center bg-[#F1F5F9] text-[10px] text-[var(--text-secondary)]">
        <ImageIcon className="mr-1 h-3 w-3" />
        {photo.filename.length > 12
          ? photo.filename.slice(0, 10) + "…"
          : photo.filename}
      </span>
      <button
        type="button"
        onClick={onRemove}
        className="absolute right-[2px] top-[2px] flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white hover:bg-black"
        aria-label={tCommon("remove")}
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

const CHECKLIST_KEYS = [
  "frame_intact",
  "no_scratches",
  "lock_aligned",
  "handle_smooth",
  "test_open_close",
  "customer_confirmed",
] as const;

export default function DoorCheckPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const t = useTranslations("techPortal.doorCheck");
  const tChecklist = useTranslations("techPortal.doorCheck.checklist");
  const tCommon = useTranslations("techPortal.common");

  const checklist = useMemo(
    () => CHECKLIST_KEYS.map((key) => ({ key, label: tChecklist(key) })),
    [tChecklist],
  );

  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [uploading, setUploading] = useState<"before" | "after" | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitOk, setSubmitOk] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const fileInputBeforeRef = useRef<HTMLInputElement>(null);
  const fileInputAfterRef = useRef<HTMLInputElement>(null);

  function toggleCheck(key: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleFileChange(
    section: "before" | "after",
    e: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(section);
    setSubmitError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append(
        "purpose",
        section === "before" ? "door_check_before" : "door_check_after",
      );
      fd.append("work_order_id", id);
      const res = await api.upload<{
        id: string;
        url: string;
        filename: string;
      }>(tenantPath("/media"), fd);
      setPhotos((prev) => [
        ...prev,
        {
          section,
          id: res.id,
          url: res.url,
          filename: res.filename,
        },
      ]);
    } catch (err) {
      setSubmitError(
        err instanceof ApiError
          ? `${err.errorCode} (${err.status})：${err.message}`
          : err instanceof Error
            ? err.message
            : String(err),
      );
    } finally {
      setUploading(null);
      // 重置 input value 以便同一張圖片可以重新選
      e.target.value = "";
    }
  }

  function removePhoto(photoId: string) {
    setPhotos((prev) => prev.filter((p) => p.id !== photoId));
  }

  const allChecked = checked.size === CHECKLIST_KEYS.length;
  const hasBefore = photos.some((p) => p.section === "before");
  const hasAfter = photos.some((p) => p.section === "after");
  const canSubmit = allChecked && hasBefore && hasAfter && !submitting;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const checklistObj = CHECKLIST_KEYS.reduce<Record<string, boolean>>(
        (acc, key) => {
          acc[key] = checked.has(key);
          return acc;
        },
        {},
      );
      // P3-KEEP: flat（無對應 v2 door-check 端點）
      await api.post(
        `/api/v1/work-orders/${encodeURIComponent(id)}/door-check`,
        {
          checklist: checklistObj,
          photos_before: photos
            .filter((p) => p.section === "before")
            .map((p) => p.url),
          photos_after: photos
            .filter((p) => p.section === "after")
            .map((p) => p.url),
          notes: notes.trim() || undefined,
        },
      );
      setSubmitOk(true);
      setTimeout(() => router.push(`/my-orders/${id}/signature`), 1500);
    } catch (e) {
      setSubmitError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <TechShell>
      <SubflowHeader workOrderId={id} title={t("title")} />

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          {t("successProceed")}
        </div>
      )}

      {submitError && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {submitError}
        </div>
      )}
      <input
        ref={fileInputBeforeRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFileChange("before", e)}
      />
      <input
        ref={fileInputAfterRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFileChange("after", e)}
      />

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("beforeLabel")}
        </span>
        <button
          type="button"
          onClick={() => fileInputBeforeRef.current?.click()}
          disabled={uploading === "before"}
          className="flex h-24 items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--border)] text-[13px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:bg-[#EFF6FF] disabled:opacity-60"
        >
          <Camera className="h-5 w-5" />
          {uploading === "before" ? tCommon("uploading") : t("captureCta")}
        </button>
        {photos.filter((p) => p.section === "before").length > 0 && (
          <div className="mt-2 grid grid-cols-3 gap-2">
            {photos
              .filter((p) => p.section === "before")
              .map((p) => (
                <PhotoThumb
                  key={p.id}
                  photo={p}
                  onRemove={() => removePhoto(p.id)}
                />
              ))}
          </div>
        )}
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("afterLabel")}
        </span>
        <button
          type="button"
          onClick={() => fileInputAfterRef.current?.click()}
          disabled={uploading === "after"}
          className="flex h-24 items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--border)] text-[13px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:bg-[#EFF6FF] disabled:opacity-60"
        >
          <Camera className="h-5 w-5" />
          {uploading === "after" ? tCommon("uploading") : t("captureCta")}
        </button>
        {photos.filter((p) => p.section === "after").length > 0 && (
          <div className="mt-2 grid grid-cols-3 gap-2">
            {photos
              .filter((p) => p.section === "after")
              .map((p) => (
                <PhotoThumb
                  key={p.id}
                  photo={p}
                  onRemove={() => removePhoto(p.id)}
                />
              ))}
          </div>
        )}
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("checklistLabel", { checked: checked.size, total: CHECKLIST_KEYS.length })}
        </span>
        {checklist.map((item) => (
          <label
            key={item.key}
            className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[13px] ${
              checked.has(item.key)
                ? "border-green-500 bg-green-50"
                : "border-[var(--border)] bg-white"
            }`}
          >
            <input
              type="checkbox"
              checked={checked.has(item.key)}
              onChange={() => toggleCheck(item.key)}
              className="h-4 w-4 accent-green-600"
            />
            {item.label}
          </label>
        ))}
      </section>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("notesLabel")}
        </span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder={t("notesPlaceholder")}
          className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
        />
      </section>

      <div className="mt-4 flex gap-2 px-4 pb-4">
        <button
          type="button"
          onClick={() => router.push(`/my-orders/${id}`)}
          className="h-12 flex-1 rounded-lg border border-[var(--border)] text-[14px] font-medium"
        >
          {tCommon("cancel")}
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className="h-12 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </div>
    </TechShell>
  );
}
