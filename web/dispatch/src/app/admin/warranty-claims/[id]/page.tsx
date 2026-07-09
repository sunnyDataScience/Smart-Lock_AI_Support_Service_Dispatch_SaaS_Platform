"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, AlertCircle, Image as ImageIcon, ExternalLink, Wrench } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, auth } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type WarrantyClaim = components["schemas"]["WarrantyClaim"];
type WarrantyClaimEnvelope = components["schemas"]["WarrantyClaimEnvelope"];
type WorkOrder = components["schemas"]["WorkOrder"];

type MediaFile = {
  id: string;
  url: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  purpose: string;
  work_order_id: string | null;
  dispute_id: string | null;
  sha256?: string | null;
  created_at: string;
};

type MediaPage = { items?: MediaFile[]; next_cursor?: string | null };

const STATUS_LABEL: Record<string, string> = {
  filed: "已申報",
  in_progress: "處理中",
  approved: "已核准",
  rejected: "已拒絕",
};

const STATUS_TONE: Record<string, { textColor: string; bgColor: string }> = {
  filed: { textColor: "#D97706", bgColor: "#FEF3C7" },
  in_progress: { textColor: "#2563EB", bgColor: "#DBEAFE" },
  approved: { textColor: "#059669", bgColor: "#D1FAE5" },
  rejected: { textColor: "#DC2626", bgColor: "#FEE2E2" },
};

function formatDate(s: string | null | undefined): string {
  if (!s) return "—";
  return s.slice(0, 10);
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function isImage(contentType: string): boolean {
  return contentType.startsWith("image/");
}

export default function WarrantyClaimDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [claim, setClaim] = useState<WarrantyClaim | null>(null);
  const [workOrder, setWorkOrder] = useState<WorkOrder | null>(null);
  const [media, setMedia] = useState<MediaFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const tenantId = auth.getTenantId();
        const tid = encodeURIComponent(tenantId);
        const env = await api.get<WarrantyClaimEnvelope>(
          `/tenants/${tid}/warranty-claims/${encodeURIComponent(id)}`,
        );
        if (!alive) return;
        const c = env.data ?? null;
        setClaim(c);

        if (c?.work_order_id) {
          try {
            const woRes = await api.get<{ data?: WorkOrder } | WorkOrder>(
              `/tenants/${tid}/work-orders/${encodeURIComponent(c.work_order_id)}`,
            );
            if (alive) {
              const wo = "data" in woRes ? (woRes as any).data : woRes;
              setWorkOrder(wo as WorkOrder);
            }
          } catch {
            // tolerate missing WO
          }
          try {
            const mediaRes = await api.get<MediaPage>(
              `/tenants/${tid}/work-orders/${encodeURIComponent(c.work_order_id)}/media`,
            );
            if (alive) setMedia(mediaRes.items ?? []);
          } catch {
            // tolerate
          }
        }
      } catch (e) {
        if (alive) {
          setError(
            friendlyError(e),
          );
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [id]);

  const tone = claim ? STATUS_TONE[claim.status] ?? { textColor: "#64748B", bgColor: "#F1F5F9" } : null;
  const evidenceMedia = media.filter((m) =>
    [
      "door_check_before",
      "door_check_after",
      "completion_before",
      "completion_after",
    ].includes(m.purpose),
  );
  const otherMedia = media.filter((m) => !evidenceMedia.includes(m));

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-2">
              <Link
                href="/admin/warranty-claims"
                className="flex items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:underline"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                返回保固索賠列表
              </Link>
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                保固索賠詳情
              </h1>
              {claim && (
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[13px] text-[var(--text-secondary)]">
                    {claim.document_number ?? claim.id.slice(0, 8)}
                  </span>
                  {tone && (
                    <span
                      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                      style={{ color: tone.textColor, backgroundColor: tone.bgColor }}
                    >
                      {STATUS_LABEL[claim.status] ?? claim.status}
                    </span>
                  )}
                  <span
                    className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                    style={{
                      color: claim.is_within_warranty ? "#059669" : "#94A3B8",
                      backgroundColor: claim.is_within_warranty ? "#D1FAE5" : "#F1F5F9",
                    }}
                  >
                    {claim.is_within_warranty ? "保固期內" : "保固期外"}
                  </span>
                </div>
              )}
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3">
              <AlertCircle className="mt-0.5 h-4 w-4 text-red-600" />
              <span className="text-sm text-red-700">{error}</span>
            </div>
          )}

          {loading && !claim && (
            <div className="flex h-[200px] items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
              <span className="text-sm text-[var(--text-secondary)]">載入中…</span>
            </div>
          )}

          {claim && (
            <>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <Card title="設備資訊">
                  <Row label="品牌">{claim.device_brand}</Row>
                  <Row label="型號">{claim.device_model}</Row>
                  <Row label="購入日期">{formatDate(claim.purchase_date)}</Row>
                </Card>

                <Card title="保固期間">
                  <Row label="保固起算">{formatDate(claim.warranty_start_date)}</Row>
                  <Row label="保固到期">{formatDate(claim.warranty_end_date)}</Row>
                  <Row label="申報日期">{formatDate(claim.claim_date)}</Row>
                </Card>

                <Card title="處理結果">
                  <Row label="折讓金額">
                    {claim.discount_offered != null
                      ? `NT$ ${Number(claim.discount_offered).toLocaleString("en-US")}`
                      : "—"}
                  </Row>
                  <Row label="處理方式">{claim.resolution ?? "—"}</Row>
                  <Row label="驗證來源">{claim.verification_source ?? "—"}</Row>
                </Card>
              </div>

              {claim.dispute_reason && (
                <Card title="申報原因">
                  <p className="whitespace-pre-wrap text-[13px] text-[var(--text-primary)]">
                    {claim.dispute_reason}
                  </p>
                </Card>
              )}

              <Card
                title="關聯工單"
                action={
                  claim.work_order_id ? (
                    <Link
                      href={`/work-orders/${claim.work_order_id}`}
                      className="flex items-center gap-1 text-[13px] text-[var(--primary)] hover:underline"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      開啟工單
                    </Link>
                  ) : null
                }
              >
                {!claim.work_order_id && (
                  <span className="text-sm text-[var(--text-secondary)]">
                    無關聯工單
                  </span>
                )}
                {claim.work_order_id && !workOrder && (
                  <span className="text-sm text-[var(--text-secondary)]">
                    載入工單中…（或工單已被移除）
                  </span>
                )}
                {workOrder && (
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <Row label="工單編號">
                      <span className="font-mono">{workOrder.id.slice(0, 8)}</span>
                    </Row>
                    <Row label="工單狀態">{workOrder.status}</Row>
                    <Row label="客戶名稱">{(workOrder as any).customer_name ?? "—"}</Row>
                    <Row label="服務地址">{(workOrder as any).customer_address ?? "—"}</Row>
                  </div>
                )}
              </Card>

              <Card
                title={`證據與媒體（${media.length}）`}
                action={
                  claim.work_order_id ? (
                    <span className="text-[12px] text-[var(--text-secondary)]">
                      來源：關聯工單上傳檔案
                    </span>
                  ) : null
                }
              >
                {!claim.work_order_id && (
                  <span className="text-sm text-[var(--text-secondary)]">
                    無關聯工單，故無可顯示之證據檔案
                  </span>
                )}
                {claim.work_order_id && media.length === 0 && (
                  <span className="text-sm text-[var(--text-secondary)]">
                    工單尚未上傳證據檔案
                  </span>
                )}
                {media.length > 0 && (
                  <div className="flex flex-col gap-4">
                    {evidenceMedia.length > 0 && (
                      <div>
                        <h3 className="mb-2 text-[12px] font-semibold text-[var(--text-secondary)]">
                          現場照片 / 完工照片（{evidenceMedia.length}）
                        </h3>
                        <MediaGrid items={evidenceMedia} />
                      </div>
                    )}
                    {otherMedia.length > 0 && (
                      <div>
                        <h3 className="mb-2 text-[12px] font-semibold text-[var(--text-secondary)]">
                          其他附件（{otherMedia.length}）
                        </h3>
                        <MediaGrid items={otherMedia} />
                      </div>
                    )}
                  </div>
                )}
              </Card>

              <Card title="時間紀錄">
                <Row label="建立時間">
                  {new Date(claim.created_at).toLocaleString("zh-TW")}
                </Row>
                <Row label="最後更新">
                  {new Date(claim.updated_at).toLocaleString("zh-TW")}
                </Row>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Card({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">{title}</h2>
        {action}
      </div>
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="w-24 shrink-0 text-[12px] text-[var(--text-secondary)]">{label}</span>
      <span className="text-[13px] text-[var(--text-primary)]">{children}</span>
    </div>
  );
}

function MediaGrid({ items }: { items: MediaFile[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {items.map((m) => (
        <a
          key={m.id}
          href={m.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col gap-1 rounded-lg border border-[var(--border)] bg-white p-2 hover:bg-[#F8FAFC]"
        >
          <div className="flex h-32 items-center justify-center overflow-hidden rounded-md bg-[#F1F5F9]">
            {isImage(m.content_type) ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={m.url}
                alt={m.filename}
                className="h-full w-full object-cover"
              />
            ) : (
              <Wrench className="h-8 w-8 text-[var(--text-disabled)]" />
            )}
          </div>
          <span className="truncate text-[12px] font-medium text-[var(--text-primary)]">
            {m.filename}
          </span>
          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
            <span>{m.purpose}</span>
            <span>{formatBytes(m.size_bytes)}</span>
          </div>
        </a>
      ))}
    </div>
  );
}
