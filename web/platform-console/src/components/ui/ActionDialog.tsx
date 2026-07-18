"use client";

// #12 平台後台美化:取代 window.prompt/confirm 的統一動作對話框。
// imperative promise API 讓呼叫端與原生 prompt 同形,每個呼叫點一行替換:
//   const v = await actionDialog.open({ title, input: {...} });
//   // resolve:string(輸入值)| true(confirm 模式)| null(取消)
// 基於 ui/Modal(Radix):focus trap、ESC 關閉、主題色票、danger 變體。
// 驗證錯誤顯示在欄位下方(不再用 window.alert 二段彈窗)。

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from "@/components/ui/Modal";
import { useTranslations } from "@/components/i18n/LocaleProvider";

export interface ActionDialogInput {
  /** 欄位標籤 */
  label: string;
  placeholder?: string;
  /** 必填最小字數;0/未給=選填(可留空送出) */
  minLength?: number;
  /** 等寬字體(代號類輸入) */
  mono?: boolean;
  /** 欄位下方輔助說明 */
  hint?: string;
}

export interface ActionDialogOptions {
  title: string;
  description?: string;
  /** 破壞性動作:確認鈕改 danger 紅 */
  danger?: boolean;
  confirmLabel?: string;
  cancelLabel?: string;
  /** 有 input=prompt 模式(resolve 輸入字串);無=confirm 模式(resolve true) */
  input?: ActionDialogInput;
}

type DialogResult = string | true | null;

interface ActionDialogContextValue {
  open: (opts: ActionDialogOptions) => Promise<DialogResult>;
}

const ActionDialogContext = createContext<ActionDialogContextValue | null>(null);

export function ActionDialogProvider({ children }: { children: ReactNode }) {
  // UAT W6-2:預設鈕文案接 i18n(caller 未給 confirmLabel/cancelLabel 時的退回值)
  const tCommon = useTranslations("common");
  const tDialog = useTranslations("components.actionDialog");
  const [opts, setOpts] = useState<ActionDialogOptions | null>(null);
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const resolverRef = useRef<((v: DialogResult) => void) | null>(null);

  const open = useCallback((o: ActionDialogOptions) => {
    return new Promise<DialogResult>((resolve) => {
      // 若前一個對話框尚未收尾(理論上不會,防禦性),視為取消
      resolverRef.current?.(null);
      resolverRef.current = resolve;
      setValue("");
      setTouched(false);
      setOpts(o);
    });
  }, []);

  const settle = useCallback((v: DialogResult) => {
    resolverRef.current?.(v);
    resolverRef.current = null;
    setOpts(null);
  }, []);

  const minLen = opts?.input?.minLength ?? 0;
  const trimmed = value.trim();
  const invalid = !!opts?.input && minLen > 0 && trimmed.length < minLen;

  function confirm() {
    if (!opts) return;
    if (opts.input) {
      if (invalid) {
        setTouched(true);
        return;
      }
      settle(trimmed);
    } else {
      settle(true);
    }
  }

  return (
    <ActionDialogContext.Provider value={{ open }}>
      {children}
      <Modal
        open={!!opts}
        onOpenChange={(o) => {
          if (!o) settle(null);
        }}
      >
        {opts && (
          <ModalContent size="sm">
            <ModalHeader>
              <ModalTitle>{opts.title}</ModalTitle>
              {opts.description && (
                <ModalDescription className="whitespace-pre-line">
                  {opts.description}
                </ModalDescription>
              )}
            </ModalHeader>

            {opts.input && (
              <div className="flex flex-col gap-1.5 px-6 py-4">
                <label
                  htmlFor="action-dialog-input"
                  className="text-[13px] font-medium text-[var(--text-primary)]"
                >
                  {opts.input.label}
                  {minLen > 0 && (
                    <span className="ml-1 text-[var(--status-danger)]" aria-hidden>
                      *
                    </span>
                  )}
                </label>
                <input
                  id="action-dialog-input"
                  autoFocus
                  type="text"
                  value={value}
                  placeholder={opts.input.placeholder}
                  onChange={(e) => setValue(e.target.value)}
                  onBlur={() => setTouched(true)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      confirm();
                    }
                  }}
                  aria-invalid={touched && invalid}
                  className={[
                    "w-full rounded-lg border bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-primary)]",
                    "placeholder:text-[var(--text-tertiary)]",
                    "focus:outline-none focus:ring-2 focus:ring-[var(--border-focus)]",
                    touched && invalid
                      ? "border-[var(--status-danger)]"
                      : "border-[var(--border)]",
                    opts.input.mono ? "font-mono" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                />
                {touched && invalid ? (
                  <p className="text-xs text-[var(--status-danger)]" role="alert">
                    {tDialog("minChars", { min: minLen })}
                  </p>
                ) : (
                  opts.input.hint && (
                    <p className="text-xs text-[var(--text-tertiary)]">{opts.input.hint}</p>
                  )
                )}
              </div>
            )}

            <ModalFooter>
              <button
                type="button"
                onClick={() => settle(null)}
                className="rounded-lg border border-[var(--border)] px-3.5 py-1.5 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)]"
              >
                {opts.cancelLabel ?? tCommon("cancel")}
              </button>
              <button
                type="button"
                onClick={confirm}
                className={`rounded-lg px-3.5 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 ${
                  opts.danger ? "bg-[var(--status-danger)]" : "bg-[var(--primary)]"
                }`}
              >
                {opts.confirmLabel ?? tCommon("confirm")}
              </button>
            </ModalFooter>
          </ModalContent>
        )}
      </Modal>
    </ActionDialogContext.Provider>
  );
}

export function useActionDialog(): ActionDialogContextValue {
  const ctx = useContext(ActionDialogContext);
  if (!ctx) {
    throw new Error("useActionDialog must be used inside <ActionDialogProvider>");
  }
  return ctx;
}
