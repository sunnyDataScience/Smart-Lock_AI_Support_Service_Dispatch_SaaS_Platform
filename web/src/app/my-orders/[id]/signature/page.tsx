"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Eraser, CheckCircle2 } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import SubflowHeader from "@/components/tech/SubflowHeader";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type SignaturePayload = components["schemas"]["SignaturePayload"];

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

interface SignaturePadProps {
  label: string;
  onChange: (dataUrl: string) => void;
}

function SignaturePad({ label, onChange }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawingRef = useRef(false);
  const tSig = useTranslations("techPortal.signature");

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = canvas.offsetWidth * 2;
    canvas.height = canvas.offsetHeight * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(2, 2);
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#1E293B";
  }, []);

  function getPoint(
    e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>,
  ): { x: number; y: number } | null {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const isTouch = "touches" in e;
    const clientX = isTouch ? e.touches[0]?.clientX : e.clientX;
    const clientY = isTouch ? e.touches[0]?.clientY : e.clientY;
    if (clientX == null || clientY == null) return null;
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  function start(
    e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>,
  ) {
    const ctx = canvasRef.current?.getContext("2d");
    const p = getPoint(e);
    if (!ctx || !p) return;
    drawingRef.current = true;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  }

  function move(
    e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>,
  ) {
    if (!drawingRef.current) return;
    const ctx = canvasRef.current?.getContext("2d");
    const p = getPoint(e);
    if (!ctx || !p) return;
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  }

  function end() {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    const canvas = canvasRef.current;
    if (canvas) {
      onChange(canvas.toDataURL("image/png"));
    }
  }

  function clear() {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (canvas && ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      onChange("");
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-medium text-[var(--text-secondary)]">
          {label}
        </span>
        <button
          type="button"
          onClick={clear}
          className="flex items-center gap-1 text-[11px] text-[var(--text-secondary)] hover:text-red-600"
        >
          <Eraser className="h-3 w-3" />
          {tSig("clear")}
        </button>
      </div>
      <canvas
        ref={canvasRef}
        onMouseDown={start}
        onMouseMove={move}
        onMouseUp={end}
        onMouseLeave={end}
        onTouchStart={start}
        onTouchMove={move}
        onTouchEnd={end}
        className="h-32 w-full rounded-lg border-2 border-dashed border-[var(--border)] bg-white touch-none"
      />
    </div>
  );
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
        `/api/v1/work-orders/${encodeURIComponent(id)}/signature`,
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
    <TechShell>
      <SubflowHeader workOrderId={id} title={t("title")} />

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          {t("successSigned")}
        </div>
      )}

      {error && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      <p className="mx-4 mt-4 text-[12px] text-[var(--text-secondary)]">
        {t("instruction")}
      </p>

      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <SignaturePad label={t("techLabel")} onChange={setTechSig} />
      </section>

      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
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
          className="h-12 flex-[2] rounded-lg bg-[var(--primary)] text-[14px] font-semibold text-white disabled:opacity-60"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </div>
    </TechShell>
  );
}
