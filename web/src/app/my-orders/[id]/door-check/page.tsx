"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Camera,
  AlertCircle,
  CheckCircle2,
  Image as ImageIcon,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";

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
  const [photos, setPhotos] = useState<{ section: "before" | "after"; name: string }[]>([]);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitOk, setSubmitOk] = useState(false);

  function toggleCheck(key: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function addPhoto(section: "before" | "after") {
    setPhotos((prev) => [
      ...prev,
      {
        section,
        name: `${section}-${prev.filter((p) => p.section === section).length + 1}.jpg`,
      },
    ]);
  }

  const allChecked = checked.size === CHECKLIST.length;
  const hasBefore = photos.some((p) => p.section === "before");
  const hasAfter = photos.some((p) => p.section === "after");
  const canSubmit = allChecked && hasBefore && hasAfter && !submitting;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      // 後端 API 待補：POST /api/v1/work-orders/{id}/door-check
      // body: { checklist, photos_before, photos_after, notes }
      await new Promise((r) => setTimeout(r, 1000));
      setSubmitOk(true);
      setTimeout(() => router.push(`/my-orders/${id}/signature`), 1500);
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

      <div className="m-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
        <AlertCircle className="mr-1 inline h-3 w-3" />
        後端 `/door-check` API 與媒體上傳待補（目前只記錄檔名 placeholder）
      </div>

      <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          作業前照片（必填，至少 1 張）
        </span>
        <button
          type="button"
          onClick={() => addPhoto("before")}
          className="flex h-24 items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--border)] text-[13px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:bg-[#EFF6FF]"
        >
          <Camera className="h-5 w-5" />
          拍照 / 選擇圖片
        </button>
        {photos.filter((p) => p.section === "before").length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {photos
              .filter((p) => p.section === "before")
              .map((p, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded bg-[#F1F5F9] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                >
                  <ImageIcon className="h-3 w-3" />
                  {p.name}
                </span>
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
          onClick={() => addPhoto("after")}
          className="flex h-24 items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--border)] text-[13px] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:bg-[#EFF6FF]"
        >
          <Camera className="h-5 w-5" />
          拍照 / 選擇圖片
        </button>
        {photos.filter((p) => p.section === "after").length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {photos
              .filter((p) => p.section === "after")
              .map((p, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded bg-[#F1F5F9] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                >
                  <ImageIcon className="h-3 w-3" />
                  {p.name}
                </span>
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
