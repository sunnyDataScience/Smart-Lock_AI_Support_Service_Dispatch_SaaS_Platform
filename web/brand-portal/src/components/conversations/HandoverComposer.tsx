"use client";

import { Send } from "lucide-react";
import { useState } from "react";
import type { components } from "@/types/api.generated";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useToast } from "@/components/ui/Toast";

type Message = components["schemas"]["Message"];

const MAX_LENGTH = 5000;

interface HandoverComposerProps {
  conversationId: string;
  /** tenant UUID（CR-0003 P2-W2 tenant-scoped v2 端點用）*/
  tenantId: string;
  /** 對話狀態為 waiting_human 時才會啟用送訊；其他狀態整個元件唯讀 */
  enabled: boolean;
  /** 訊息成功送出後通知上層 refetch / append */
  onSent: (msg: Message) => void;
  /**
   * 客服主動接管（active → escalated）。2026-08-02 新增。
   *
   * 放在這裡而不是頁面別處：`enabled=false` 時客服的視線正好落在下面那行
   * 「僅在對話被升級為…」的提示上——那是他被擋住的當下。把自救按鈕放在
   * 別的地方等於沒做（業主 2026-08-01 卡住時，全站根本沒有任何入口）。
   * 未傳則不顯示按鈕（沿用舊行為）。
   */
  onRequestHandover?: () => void;
  /** 接管請求進行中（避免連點） */
  requestingHandover?: boolean;
}

/**
 * HandoverComposer — 客服接管後的發訊 input。
 *
 * 對應 BE: POST /tenants/{tenantId}/conversations/{id}/messages（operationId: sendChatMessage）。
 * CR-0003 P2-W2：已遷移至 tenant-scoped v2 端點（FR-0018）。
 * - textarea + 5000 字計數
 * - api.post 自動帶 Idempotency-Key（lib/api.ts 預設行為）
 * - useToast 反饋成功 / 失敗
 */
export default function HandoverComposer({
  conversationId,
  tenantId,
  enabled,
  onSent,
  onRequestHandover,
  requestingHandover = false,
}: HandoverComposerProps) {
  const { toast } = useToast();
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);

  const trimmed = content.trim();
  const overLimit = content.length > MAX_LENGTH;
  const canSend = enabled && !sending && trimmed.length > 0 && !overLimit;

  const handleSend = async () => {
    if (!canSend) return;
    setSending(true);
    try {
      // CR-0003 P2-W2：tenant-scoped v2 端點
      const msg = await api.post<Message>(
        `/tenants/${encodeURIComponent(tenantId)}/conversations/${encodeURIComponent(conversationId)}/messages`,
        { content: trimmed },
      );
      onSent(msg);
      setContent("");
      toast({ title: "已發送", variant: "success" });
    } catch (e) {
      const message =
        friendlyError(e);
      toast({ title: "發送失敗", description: message, variant: "error" });
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Cmd/Ctrl + Enter 快速送出（與一般 Enter 換行區隔）
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col gap-2 border-t border-[var(--border)] bg-[var(--bg-surface)] p-4">
      {!enabled && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-[12px] text-[var(--text-secondary)]">
            僅在對話被升級為「等待人工」狀態時可發送訊息
          </div>
          {onRequestHandover && (
            <button
              type="button"
              onClick={onRequestHandover}
              disabled={requestingHandover}
              className="shrink-0 rounded-md border border-[var(--primary)] px-3 py-1.5 text-[13px] font-medium text-[var(--primary)] transition-colors hover:bg-[var(--primary-light)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] disabled:opacity-50"
            >
              {requestingHandover ? "接管中…" : "接管對話"}
            </button>
          )}
        </div>
      )}

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={!enabled || sending}
        rows={3}
        maxLength={MAX_LENGTH + 1 /* 讓 overLimit 偵測能觸發、UI 上仍呈現紅字 */}
        placeholder={
          enabled
            ? "輸入要回覆給用戶的訊息…（Cmd/Ctrl + Enter 快速送出）"
            : "目前對話狀態不允許客服直接發訊"
        }
        className="w-full resize-none rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-60"
      />

      <div className="flex items-center justify-between">
        <span
          className={`text-[12px] ${
            overLimit ? "text-[var(--status-danger)]" : "text-[var(--text-secondary)]"
          }`}
        >
          {content.length} / {MAX_LENGTH}
        </span>
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          className="flex items-center gap-[6px] rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
          {sending ? "發送中…" : "發送"}
        </button>
      </div>
    </div>
  );
}
