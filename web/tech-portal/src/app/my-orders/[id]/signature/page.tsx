"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SignaturePad from "@/components/tech/SignaturePad";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type SignaturePayload = components["schemas"]["SignaturePayload"];

function formatErr(e: unknown): string {
  return friendlyError(e);
}

export default function SignaturePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const t = useTranslations("techPortal.signature");
  const tCommon = useTranslations("techPortal.common");

  const [techSig, setTechSig] = useState("");
  const [custSig, setCustSig] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitOk, setSubmitOk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = techSig.length > 100 && custSig.length > 100 && !submitting;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const body: SignaturePayload = {
        customer_signature: custSig,
        technician_signature: techSig,
        signed_at: new Date().toISOString(),
      };
      // 嘗試取得 GPS（不阻塞）
      if (typeof navigator !== "undefined" && navigator.geolocation) {
        try {
          const pos = await new Promise<GeolocationPosition>(
            (resolve, reject) => {
              navigator.geolocation.getCurrentPosition(resolve, reject, {
                timeout: 3000,
              });
            },
          );
          body.gps_lat = pos.coords.latitude;
          body.gps_lng = pos.coords.longitude;
        } catch {
          // 忽略 GPS 取得失敗
        }
      }
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(id)}/signature`),
        body,
      );
      setSubmitOk(true);
      setTimeout(() => router.push(`/my-orders/${id}`), 1500);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <TechShell
      // 頁首走 shell 統一規格(h-14 bar:返回工單詳情 + 編號 kicker + 標題)
      backHref={`/my-orders/${id}`}
      kicker={`#${id.slice(0, 8)}`}
      title={t("title")}
    >

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          {t("successSigned")}
        </div>
      )}

      {error && (
        <div className="m-4 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      <p className="mx-4 mt-4 text-[12px] text-[var(--text-secondary)]">
        {t("instruction")}
      </p>

      <section className="mx-4 mt-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
        <SignaturePad label={t("techLabel")} onChange={setTechSig} />
      </section>

      <section className="mx-4 mt-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
        <SignaturePad label={t("customerLabel")} onChange={setCustSig} />
      </section>

      <p className="mx-4 mt-4 text-[11px] text-[var(--text-disabled)]">
        {t("uploadHint", { id })}
      </p>

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
          className="h-12 flex-[2] rounded-full bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </div>
    </TechShell>
  );
}
