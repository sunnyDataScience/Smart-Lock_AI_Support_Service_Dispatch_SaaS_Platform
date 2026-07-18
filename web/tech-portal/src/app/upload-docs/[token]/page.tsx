"use client";

import { Check, FileUp, Link2Off } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import DocUploadSlots, {
  useRegistrationDocUpload,
} from "@/components/tech/RegistrationDocUpload";

// ── /upload-docs/[token] 師傅補件獨立頁（W3-6 免 email 自助方案）─────────────
// 免登入公開頁（AuthGuard PUBLIC_PREFIXES 已列 /upload-docs/，比照 /track 等
// token 公開頁慣例）：平台 admin 於平台 console 對 pending 師傅簽發補件 token
// （POST /platform/technicians/{id}:issue-upload-token），連結交付師傅後憑
// token 打既有公開上傳端點（與 /tech-register 內嵌步驟共用 RegistrationDocUpload）。
//
// token 驗證時機：後端無獨立驗證端點（防探測：上傳端點才驗、單一錯誤碼），
// 故載入即渲染上傳 UI；首次上傳收到 403 UPLOAD_TOKEN_INVALID 即切換為
// 「連結已失效」畫面，不會白屏。

type View = "form" | "done" | "invalid";

export default function UploadDocsPage() {
  const t = useTranslations("techPortal.docUpload.page");
  const params = useParams<{ token: string }>();
  const token = typeof params?.token === "string" ? params.token : "";

  // token 段缺失（理論上路由保證存在，防呆）→ 直接視為無效連結
  const [view, setView] = useState<View>(token ? "form" : "invalid");
  const ctrl = useRegistrationDocUpload(token, {
    onTokenInvalid: () => setView("invalid"),
  });

  return (
    <div className="tech-soft relative flex min-h-screen items-start justify-center bg-[var(--bg-page)] px-4 py-8 md:items-center">
      <div className="absolute right-4 top-4">
        <LocaleToggle />
      </div>

      <div className="w-full max-w-[560px] rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-6 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))] md:p-8">
        {view === "invalid" ? (
          <InvalidView uploadedCount={ctrl.uploadedCount} />
        ) : view === "done" ? (
          <DoneView />
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col items-center gap-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)]">
                <FileUp className="h-6 w-6 text-white" />
              </div>
              <h1 className="text-xl font-bold text-[var(--text-primary)]">{t("title")}</h1>
              <p className="text-center text-sm text-[var(--text-secondary)]">
                {t("subtitle")}
              </p>
            </div>

            <DocUploadSlots ctrl={ctrl} />

            <p className="text-center text-xs text-[var(--text-disabled)]">{t("hint")}</p>

            <button
              type="button"
              onClick={() => setView("done")}
              disabled={ctrl.uploadedCount === 0 || !!ctrl.uploading}
              className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-60"
            >
              {ctrl.uploadedCount > 0
                ? t("submit", { count: ctrl.uploadedCount })
                : t("submitEmpty")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function DoneView() {
  const t = useTranslations("techPortal.docUpload.page");
  return (
    <div className="flex flex-col items-center gap-4 py-6">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-100">
        <Check className="h-7 w-7 text-green-600" />
      </div>
      <p className="text-base font-semibold text-[var(--text-primary)]">{t("doneTitle")}</p>
      <p className="text-center text-sm text-[var(--text-secondary)]">{t("doneBody")}</p>
      <p className="text-center text-xs text-[var(--text-disabled)]">{t("doneClose")}</p>
    </div>
  );
}

function InvalidView({ uploadedCount }: { uploadedCount: number }) {
  const t = useTranslations("techPortal.docUpload.page");
  return (
    <div className="flex flex-col items-center gap-4 py-6">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
        <Link2Off className="h-7 w-7 text-red-500" />
      </div>
      <p className="text-base font-semibold text-[var(--text-primary)]">
        {t("invalidTitle")}
      </p>
      <p className="text-center text-sm text-[var(--text-secondary)]">{t("invalidBody")}</p>
      {uploadedCount > 0 && (
        // 中途失效（如上傳次數用罄）：先前成功的檔案已送出，避免師傅誤以為全部要重來
        <p className="text-center text-xs text-[var(--text-disabled)]">
          {t("invalidUploadedNote", { count: uploadedCount })}
        </p>
      )}
    </div>
  );
}
