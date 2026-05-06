"use client";

import { useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Camera,
  CheckCircle2,
  Image as ImageIcon,
  X,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";
import { ApiError, api } from "@/lib/api";

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
        aria-label="移除"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

const CHECKLIST = [
  { key: "frame_intact", label: "門框完整無變形" },
  { key: "no_scratches", label: "門板無新刮痕" },
  { key: "lock_aligned", label: "鎖具對位正確" },
  { key: "handle_smooth", label: "把手轉動順暢" },
  { key: "test_open_close", label: "已測試開關閉合 5 次以上" },
  { key: "customer_confirmed", label: "客戶已現場確認外觀" },
];

export default function DoorCheckPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();

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
      }>("/api/v1/media", fd);
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

  const allChecked = checked.size === CHECKLIST.length;
  const hasBefore = photos.some((p) => p.section === "before");
  const hasAfter = photos.some((p) => p.section === "after");
  const canSubmit = allChecked && hasBefore && hasAfter && !submitting;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const checklistObj = CHECKLIST.reduce<Record<string, boolean>>(
        (acc, item) => {
          acc[item.key] = checked.has(item.key);
          return acc;
        },
        {},
      );
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
      <SubflowHeader workOrderId={id} title="門面外觀檢核" />

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          檢核完成，前往簽章流程
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
          作業前照片（必填，至少 1 張）
        </span>
        <button
          type="button"
          onClick={() => fileInputBeforeRef.current?.click()}
          disabled={uploading === "before"}
          className="flex h-24 items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--border)] text-[13px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:bg-[#EFF6FF] disabled:opacity-60"
        >
          <Camera className="h-5 w-5" />
          {uploading === "before" ? "上傳中…" : "拍照 / 選擇圖片"}
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
          作業後照片（必填，至少 1 張）
        </span>
        <button
          type="button"
          onClick={() => fileInputAfterRef.current?.click()}
          disabled={uploading === "after"}
          className="flex h-24 items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--border)] text-[13px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:bg-[#EFF6FF] disabled:opacity-60"
        >
          <Camera className="h-5 w-5" />
          {uploading === "after" ? "上傳中…" : "拍照 / 選擇圖片"}
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
          檢核項目（{checked.size} / {CHECKLIST.length}）
        </span>
        {CHECKLIST.map((item) => (
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
          備註（選填）
        </span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="例：原舊鎖芯有輕微生鏽，安裝後一切正常..."
          className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px]"
        />
      </section>

      <div className="mt-4 flex gap-2 px-4 pb-4">
        <button
          type="button"
          onClick={() => router.push(`/my-orders/${id}`)}
          className="h-12 flex-1 rounded-lg border border-[var(--border)] text-[14px] font-medium"
        >
          取消
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className="h-12 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? "提交中…" : "完成檢核 → 進簽章"}
        </button>
      </div>
    </TechShell>
  );
}
