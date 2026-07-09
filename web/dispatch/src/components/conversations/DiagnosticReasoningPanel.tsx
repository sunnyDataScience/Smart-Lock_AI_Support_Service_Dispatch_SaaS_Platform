"use client";

import { useEffect, useRef, useState } from "react";
import { Brain, ChevronDown, ChevronUp, X } from "lucide-react";
import RealtimeIndicator from "@/components/realtime/RealtimeIndicator";
import { useSSEChannel } from "@/hooks/useSSEChannel";

interface DiagnosticStep {
  step_index: number;
  content_delta: string;
  is_final?: boolean;
}

interface Props {
  conversationId: string;
  /** 訂閱啟用旗標（預設 true）。 */
  enabled?: boolean;
  /** 預設展開 */
  defaultOpen?: boolean;
}

/**
 * AI 診斷推理串流面板（A32）。訂閱 /realtime/diagnostics/{conv_id}，
 * 累加 content_delta，is_final=true 時鎖定。
 */
export default function DiagnosticReasoningPanel({
  conversationId,
  enabled = true,
  defaultOpen = false,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [steps, setSteps] = useState<DiagnosticStep[]>([]);
  const [done, setDone] = useState(false);
  const scrollerRef = useRef<HTMLDivElement>(null);

  const { status } = useSSEChannel<DiagnosticStep>({
    channelPath: conversationId
      ? `/realtime/diagnostics/${conversationId}`
      : "",
    enabled: !!conversationId && enabled && !done,
    eventNames: ["diagnostic.reasoning.step"],
    onMessage: (msg) => {
      const data = (msg.payload ?? msg) as DiagnosticStep | undefined;
      if (!data || typeof data.step_index !== "number") return;
      setSteps((prev) => {
        const exists = prev.findIndex((s) => s.step_index === data.step_index);
        if (exists >= 0) {
          // 同 step_index 視為 token 累加
          const next = [...prev];
          next[exists] = {
            ...next[exists],
            content_delta:
              (next[exists].content_delta ?? "") + (data.content_delta ?? ""),
            is_final: data.is_final ?? next[exists].is_final,
          };
          return next;
        }
        return [...prev, data];
      });
      if (data.is_final) setDone(true);
    },
  });

  // auto scroll 至底（僅在 open 且新增 step 時）
  useEffect(() => {
    if (open && scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [steps, open]);

  function reset() {
    setSteps([]);
    setDone(false);
  }

  if (!conversationId) return null;

  return (
    <section className="rounded-xl border border-[var(--border)] bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-[var(--primary)]" />
          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
            AI 診斷推理
          </span>
          {steps.length > 0 && (
            <span className="rounded bg-[#EFF6FF] px-2 py-[1px] text-[11px] font-medium text-[var(--primary)]">
              {steps.length} 步
            </span>
          )}
          {done && (
            <span className="rounded bg-green-50 px-2 py-[1px] text-[11px] font-medium text-green-700">
              完成
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <RealtimeIndicator status={status} compact />
          {open ? (
            <ChevronUp className="h-4 w-4 text-[var(--text-secondary)]" />
          ) : (
            <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
          )}
        </div>
      </button>

      {open && (
        <div className="border-t border-[var(--border)]">
          <div
            ref={scrollerRef}
            className="max-h-[320px] overflow-y-auto px-4 py-3"
          >
            {steps.length === 0 ? (
              <p className="text-[12px] text-[var(--text-disabled)]">
                {status === "open"
                  ? "等待診斷推理串流…"
                  : status === "disabled"
                    ? "即時推送服務尚未啟用，請聯絡系統管理員"
                    : "尚未開始或頻道未啟動"}
              </p>
            ) : (
              <ol className="flex flex-col gap-2">
                {steps
                  .slice()
                  .sort((a, b) => a.step_index - b.step_index)
                  .map((s) => (
                    <li
                      key={s.step_index}
                      className="rounded-md bg-[#F8FAFC] p-3"
                    >
                      <div className="mb-1 flex items-center gap-2">
                        <span className="rounded bg-[var(--primary)] px-2 py-[1px] text-[10px] font-bold text-white">
                          STEP {s.step_index + 1}
                        </span>
                        {s.is_final && (
                          <span className="text-[10px] text-green-700">
                            ★ 最終結論
                          </span>
                        )}
                      </div>
                      <pre className="whitespace-pre-wrap break-words font-sans text-[12px] leading-[1.6] text-[var(--text-primary)]">
                        {s.content_delta}
                      </pre>
                    </li>
                  ))}
              </ol>
            )}
          </div>

          {steps.length > 0 && (
            <div className="flex items-center justify-end gap-2 border-t border-[var(--border)] px-4 py-2">
              <button
                type="button"
                onClick={reset}
                className="flex items-center gap-1 text-[11px] text-[var(--text-secondary)] hover:text-red-600"
              >
                <X className="h-3 w-3" />
                清除並重新訂閱
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
