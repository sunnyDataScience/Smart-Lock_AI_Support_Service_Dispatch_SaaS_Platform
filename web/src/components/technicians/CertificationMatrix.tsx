"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";

/* CR-0104：技能認證矩陣（真資料）— 讀 GET /tenants/{tid}/technicians/{id}/certifications。
   CR-0114 收斂：認證屬師傅身分域資質，歸平台方職權 —— 品牌端改為完全唯讀
   （原新增/編輯/刪除已移除；認證登錄途徑=師傅自助註冊，平台方管理為後續輪）。
   狀態（有效/即將到期/已過期）由後端依到期日 computed。 */

interface Certification {
  id: string;
  technician_id: string;
  cert_name: string;
  brand: string | null;
  obtained_at: string | null;
  expires_at: string | null;
  status: "valid" | "expiring_soon" | "expired";
  is_mock: boolean;
  created_at: string | null;
}

const STATUS_STYLE: Record<
  Certification["status"],
  { label: string; textColor: string; bgColor: string }
> = {
  valid: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" },
  expiring_soon: { label: "即將到期", textColor: "#92400E", bgColor: "#FEF3C7" },
  expired: { label: "已過期", textColor: "#991B1B", bgColor: "#FEE2E2" },
};

function fmtDate(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "—";
}

interface Props {
  tenantId: string;
  technicianId: string;
}

export default function CertificationMatrix({ tenantId, technicianId }: Props) {
  const [certs, setCerts] = useState<Certification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const basePath = `/tenants/${encodeURIComponent(tenantId)}/technicians/${encodeURIComponent(technicianId)}/certifications`;

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.get<{ data: Certification[] }>(basePath);
      setCerts(res.data ?? []);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    }
  }, [basePath]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      await load();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">技能認證矩陣</h2>
        <span className="text-[12px] text-[var(--text-secondary)]">認證資料由平台方管理</span>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        <div className="flex h-[40px] items-center bg-[var(--bg-page)] px-4">
          <div className="flex w-[180px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">認證項目</span></div>
          <div className="flex w-[110px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">品牌</span></div>
          <div className="flex w-[110px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">取得日期</span></div>
          <div className="flex w-[110px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">到期日期</span></div>
          <div className="flex w-[90px]"><span className="text-[12px] font-semibold text-[var(--text-secondary)]">狀態</span></div>
        </div>

        {loading ? (
          <div className="flex h-[60px] items-center justify-center text-[13px] text-[var(--text-disabled)]">載入中…</div>
        ) : certs.length === 0 ? (
          <div className="flex h-[60px] items-center justify-center text-[13px] text-[var(--text-disabled)]">
            尚無認證資料（師傅註冊時填報，或由平台方登錄）。
          </div>
        ) : (
          certs.map((c, idx) => {
            const st = STATUS_STYLE[c.status] ?? STATUS_STYLE.valid;
            return (
              <div
                key={c.id}
                className={`flex h-[44px] items-center px-4 ${idx < certs.length - 1 ? "border-b border-[var(--border)]" : ""}`}
              >
                <div className="flex w-[180px]"><span className="text-[13px] text-[var(--text-primary)]">{c.cert_name}</span></div>
                <div className="flex w-[110px]"><span className="text-[13px] text-[var(--text-primary)]">{c.brand || "—"}</span></div>
                <div className="flex w-[110px]"><span className="text-[13px] text-[var(--text-primary)]">{fmtDate(c.obtained_at)}</span></div>
                <div className="flex w-[110px]"><span className="text-[13px] text-[var(--text-primary)]">{fmtDate(c.expires_at)}</span></div>
                <div className="flex w-[90px]">
                  <span
                    className="rounded-full px-[10px] py-[2px] text-[11px] font-medium"
                    style={{ color: st.textColor, backgroundColor: st.bgColor }}
                  >
                    {st.label}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
