"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

interface Props {
  workOrderId: string;
  title: string;
  /** 預設返回 /my-orders/[id]；可指定其他路徑 */
  backTo?: string;
}

export default function SubflowHeader({ workOrderId, title, backTo }: Props) {
  const router = useRouter();
  const target = backTo ?? `/my-orders/${workOrderId}`;
  return (
    <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--border)] bg-white px-2 py-3">
      <button
        type="button"
        onClick={() => router.push(target)}
        className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
        aria-label="返回"
      >
        <ArrowLeft className="h-5 w-5" />
      </button>
      <div className="flex flex-1 flex-col">
        <span className="text-[11px] text-[var(--text-disabled)]">
          #{workOrderId.slice(0, 8)}
        </span>
        <span className="text-[15px] font-semibold text-[var(--text-primary)]">
          {title}
        </span>
      </div>
    </div>
  );
}
