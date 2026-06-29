"use client";

import { use, useEffect, useState } from "react";
import { ChevronRight, Pencil, Ban, RotateCcw, Star, Info, X } from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import TechnicianDetailSidebar from "@/components/technicians/TechnicianDetailSidebar";
import CertificationMatrix from "@/components/technicians/CertificationMatrix";
import { ApiError, api, getCurrentSession, FALLBACK_TENANT_ID } from "@/lib/api";
import { cacheInvalidate } from "@/lib/cache";
import { LOCK_BRANDS_HINT } from "@/lib/constants/brands";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type TechnicianEnvelope = components["schemas"]["TechnicianEnvelope"];
type Availability = Technician["availability"];

const AVAILABILITY_STYLE: Record<Availability, { label: string; textColor: string; bgColor: string }> = {
  available: { label: "可用", textColor: "#065F46", bgColor: "#D1FAE5" },
  busy: { label: "外出中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
  offline: { label: "離線", textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" },
  on_leave: { label: "休假中", textColor: "#92400E", bgColor: "#FEF3C7" },
  circuit_breaker_open: { label: "暫停派工", textColor: "#991B1B", bgColor: "#FEE2E2" },
};

const BRAND_STYLE: Record<string, { textColor: string; bgColor: string }> = {
  Yale: { textColor: "#92400E", bgColor: "#FEF3C7" },
  Chatlock: { textColor: "#3730A3", bgColor: "#E0E7FF" },
  美樂: { textColor: "#065F46", bgColor: "#D1FAE5" },
  "Mi-La": { textColor: "#065F46", bgColor: "#D1FAE5" },
  Dormakaba: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
};

const FALLBACK_BRAND = { textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" };

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return iso.slice(0, 10);
  } catch {
    return "—";
  }
}

function ProfileCard({ technician }: { technician: Technician }) {
  const ratingFloor = Math.floor(technician.rating);
  const completed = technician.completed_orders_count ?? 0;
  const region = (technician.service_areas ?? []).join("、") || "—";
  const skills = technician.skills ?? [];

  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
        個人資料
      </h2>
      <div className="flex gap-6">
        <div className="flex flex-col items-center gap-2">
          <div className="h-[80px] w-[80px] flex-shrink-0 rounded-full bg-[#DBEAFE]" />
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((i) => (
              <Star
                key={i}
                className={
                  i <= ratingFloor
                    ? "h-4 w-4 fill-[var(--accent)] text-[var(--accent)]"
                    : "h-4 w-4 text-[var(--border)]"
                }
              />
            ))}
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              {technician.rating.toFixed(1)}
            </span>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-3">
          <div className="flex gap-4">
            <Field label="姓名" value={technician.name} />
            <Field label="電話" value={technician.phone} mono />
            <Field label="服務區域" value={region} />
          </div>
          <div className="flex gap-4">
            <Field label="入職日期" value={formatDate(technician.created_at)} />
            <Field label="等級" value={technician.level} />
            <Field
              label="完成工單"
              value={`${completed} 件`}
              color="var(--primary)"
              bold
            />
          </div>
          <div className="flex flex-col gap-[6px]">
            <span className="text-[12px] text-[var(--text-secondary)]">
              專長品牌
            </span>
            <div className="flex flex-wrap gap-[6px]">
              {skills.length > 0 ? (
                skills.map((b) => {
                  const style = BRAND_STYLE[b] ?? FALLBACK_BRAND;
                  return (
                    <span
                      key={b}
                      className="rounded-md px-3 py-1 text-[12px] font-medium"
                      style={{ color: style.textColor, backgroundColor: style.bgColor }}
                    >
                      {b}
                    </span>
                  );
                })
              ) : (
                <span className="text-[12px] text-[var(--text-disabled)]">—</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  color,
  bold,
  mono,
}: {
  label: string;
  value: string;
  color?: string;
  bold?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col gap-1">
      <span className="text-[12px] text-[var(--text-secondary)]">{label}</span>
      <span
        className={`text-[14px] ${bold ? "font-semibold" : "font-medium"} ${mono ? "font-['IBM_Plex_Mono']" : ""}`}
        style={{ color: color || "var(--text-primary)" }}
      >
        {value}
      </span>
    </div>
  );
}

/* ─── Mock Sections（本週排班仍為示意；技能認證矩陣已改真資料 CertificationMatrix）─── */

const scheduleDays = [
  { dayLabel: "週一", date: "20", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週二", date: "21", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週三", date: "22", shift: "晚班", shiftTextColor: "#3730A3", bgColor: "#E0E7FF", isToday: true },
  { dayLabel: "週四", date: "23", shift: "晚班", shiftTextColor: "#3730A3", bgColor: "#E0E7FF" },
  { dayLabel: "週五", date: "24", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週六", date: "25", shift: "值班", shiftTextColor: "#92400E", bgColor: "#FEF3C7" },
  { dayLabel: "週日", date: "26", shift: "休息", shiftTextColor: "var(--text-disabled)", bgColor: "var(--bg-page)", hasBorder: true },
];

function WeeklySchedule() {
  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">本週排班</h2>
        <span className="text-[13px] text-[var(--text-secondary)]">2026/04/20 - 2026/04/26</span>
      </div>
      <div className="flex gap-[6px]">
        {scheduleDays.map((d) => (
          <div key={d.dayLabel} className="flex flex-1 flex-col items-center gap-1">
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">{d.dayLabel}</span>
            <span className="text-[11px]" style={{ color: d.isToday ? "var(--primary)" : "var(--text-secondary)" }}>
              {d.date}
            </span>
            <div
              className="flex h-12 w-full items-center justify-center rounded-md"
              style={{
                backgroundColor: d.bgColor,
                border: d.hasBorder ? "1px solid var(--border)" : undefined,
              }}
            >
              <span className="text-[11px] font-medium" style={{ color: d.shiftTextColor }}>
                {d.shift}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function MockBanner() {
  return (
    <div className="mx-8 mt-4 flex items-start gap-2 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] px-4 py-3">
      <Info className="mt-[2px] h-4 w-4 flex-shrink-0 text-[var(--text-secondary)]" />
      <span className="text-[12px] text-[var(--text-secondary)]">
        以下「本週排班」為示意，待排班模組接入後將顯示真實資料；「技能認證矩陣」、右側「可用狀態」「佣金摘要」「獎懲紀錄」與「進行中工單」已連線真實資料。
      </span>
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────────────────── */

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function TechnicianDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const [technician, setTechnician] = useState<Technician | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // CR-0103 操作狀態（停權/復權/編輯）
  const [actionBusy, setActionBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({ name: "", phone: "", skills: "", regions: "", level: "" });

  // CR-0002-α：遷移至 tenant-scoped v2 端點
  const session = getCurrentSession();
  const tenantId = session?.tenantId ?? FALLBACK_TENANT_ID;

  async function loadTechnician() {
    setError(null);
    try {
      const res = await api.get<TechnicianEnvelope>(
        `/tenants/${encodeURIComponent(tenantId)}/technicians/${encodeURIComponent(id)}`,
      );
      setTechnician(res.data ?? null);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    }
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      await loadTechnician();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, tenantId]);

  // CR-0103：停權/復權 — 接 technician_lifecycle_v2 :suspend/:reactivate（需 X-Initiator + reason）
  async function handleLifecycle(action: "suspend" | "reactivate") {
    const initiator = session?.userId ?? "";
    if (!initiator) {
      setActionMsg("缺少操作者身分（請重新登入）");
      return;
    }
    const verb = action === "suspend" ? "停權" : "復權";
    // 後端 technician_lifecycle_service `_change_status_and_audit` 要求 reason
    // strip 後 ≥3 字元，否則 VALIDATION_ERROR (422)。前端先擋並在邊界提示，
    // 避免送出才得語意不明的 422（業主回報只看到「VALIDATION_ERROR (422)」）。
    const reason = window.prompt(`請輸入${verb}原因（至少 3 個字，會記入稽核紀錄）：`, "");
    if (reason == null) return; // 取消 → 不送
    if (reason.trim().length < 3) {
      setActionMsg(`${verb}原因至少需 3 個字`);
      return;
    }
    setActionBusy(true);
    setActionMsg(null);
    try {
      await api.post(
        `/tenants/${encodeURIComponent(tenantId)}/technicians/${encodeURIComponent(id)}:${action}`,
        { reason: reason.trim() },
        { headers: { "X-Initiator": initiator } },
      );
      cacheInvalidate("GET:"); // 清 30s GET 快取，讓 refetch 取到更新後狀態
      await loadTechnician();
    } catch (e) {
      // ApiError.message 帶後端友善 detail（如「reason 至少 3 字元」/狀態衝突），
      // 一併顯示比裸 errorCode 更可行動。
      setActionMsg(
        e instanceof ApiError
          ? `${verb}失敗：${e.message || e.errorCode}（${e.status}）`
          : `${verb}失敗`,
      );
    } finally {
      setActionBusy(false);
    }
  }

  // CR-0103：開啟編輯（用目前資料預填姓名/電話/技能/區域）
  function openEdit() {
    if (!technician) return;
    setEditForm({
      name: technician.name ?? "",
      phone: technician.phone ?? "",
      skills: (technician.skills ?? []).join(", "),
      regions: (technician.service_areas ?? []).join(", "),
      level: technician.level ?? "",
    });
    setActionMsg(null);
    setEditOpen(true);
  }

  // CR-0103：儲存編輯 — PATCH updateTechnicianV2（部分更新；逗號分隔轉陣列）
  async function handleSaveEdit() {
    const splitCsv = (s: string) =>
      s.split(/[,，]/).map((x) => x.trim()).filter(Boolean);
    setActionBusy(true);
    setActionMsg(null);
    try {
      await api.patch(
        `/tenants/${encodeURIComponent(tenantId)}/technicians/${encodeURIComponent(id)}`,
        {
          display_name: editForm.name.trim() || undefined,
          phone: editForm.phone.trim() || undefined,
          capabilities: splitCsv(editForm.skills),
          coverage_areas: splitCsv(editForm.regions),
          level: editForm.level || undefined,
        },
      );
      cacheInvalidate("GET:"); // 清 30s GET 快取，讓 refetch 取到更新後資料
      setEditOpen(false);
      await loadTechnician();
    } catch (e) {
      setActionMsg(
        e instanceof ApiError ? `儲存失敗：${e.errorCode} (${e.status})` : "儲存失敗",
      );
    } finally {
      setActionBusy(false);
    }
  }

  const status = technician
    ? AVAILABILITY_STYLE[technician.availability] ?? AVAILABILITY_STYLE.available
    : null;
  const shortId = id.slice(0, 8);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-y-auto">
          {/* Header */}
          <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
            <div className="flex items-center gap-[6px]">
              <Link href="/technicians" className="text-[13px] text-[var(--primary)] hover:underline">
                技師管理
              </Link>
              <ChevronRight className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
              <span className="text-[13px] text-[var(--text-secondary)]">
                {technician?.name ?? shortId}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
                  {loading && !technician ? "載入中…" : technician?.name ?? "—"}
                </h1>
                {status && (
                  <span
                    className="rounded-full px-3 py-1 text-[12px] font-medium"
                    style={{ color: status.textColor, backgroundColor: status.bgColor }}
                  >
                    {status.label}
                  </span>
                )}
                <span className="font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-secondary)]" title={id}>
                  ID: {shortId}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={openEdit}
                  disabled={!technician || actionBusy}
                  className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] px-4 py-2 hover:bg-[var(--bg-page)] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Pencil className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
                  <span className="text-[13px] text-[var(--text-primary)]">編輯</span>
                </button>
                {/* 停權/復權依 onboarding 狀態切換（接 lifecycle :suspend/:reactivate）；
                    pending_approval/terminated 等狀態不顯示（核准在列表頁、終止為不可逆另議）。 */}
                {technician?.status === "active" && (
                  <button
                    onClick={() => handleLifecycle("suspend")}
                    disabled={actionBusy}
                    className="flex items-center gap-[6px] rounded-lg border border-[var(--error)] px-4 py-2 hover:bg-red-50 disabled:opacity-50"
                  >
                    <Ban className="h-[14px] w-[14px] text-[var(--error)]" />
                    <span className="text-[13px] text-[var(--error)]">停權</span>
                  </button>
                )}
                {technician?.status === "suspended" && (
                  <button
                    onClick={() => handleLifecycle("reactivate")}
                    disabled={actionBusy}
                    className="flex items-center gap-[6px] rounded-lg border border-[var(--primary)] px-4 py-2 hover:bg-[var(--primary-light)] disabled:opacity-50"
                  >
                    <RotateCcw className="h-[14px] w-[14px] text-[var(--primary)]" />
                    <span className="text-[13px] text-[var(--primary)]">復權</span>
                  </button>
                )}
              </div>
            </div>
          </div>

          {error && (
            <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入技師失敗：{error}
            </div>
          )}

          {actionMsg && !editOpen && (
            <div className="mx-8 mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {actionMsg}
            </div>
          )}

          {technician ? (
            <>
              <ProfileCard technician={technician} />
              <MockBanner />
              <CertificationMatrix tenantId={tenantId} technicianId={id} />
              <WeeklySchedule />
            </>
          ) : (
            !loading && !error && (
              <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-secondary)]">
                找不到此技師
              </div>
            )
          )}
        </div>

        <TechnicianDetailSidebar technicianId={id} availability={technician?.availability} />
      </div>

      {/* CR-0103 編輯技師基本資料 modal（姓名/電話/技能/區域；狀態變更走停權/復權鈕）*/}
      {editOpen && technician && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-[var(--bg-surface)] p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">編輯技師資料</h2>
              <button
                onClick={() => setEditOpen(false)}
                aria-label="關閉"
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">姓名</span>
                <input
                  value={editForm.name}
                  onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">聯絡電話</span>
                <input
                  value={editForm.phone}
                  onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">等級</span>
                <select
                  value={editForm.level}
                  onChange={(e) => setEditForm((f) => ({ ...f, level: e.target.value }))}
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                >
                  <option value="S">S（頂級）</option>
                  <option value="A">A（資深）</option>
                  <option value="B">B（中級）</option>
                  <option value="C">C（入門）</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">技能 / 品牌（逗號分隔）</span>
                <input
                  value={editForm.skills}
                  onChange={(e) => setEditForm((f) => ({ ...f, skills: e.target.value }))}
                  placeholder={LOCK_BRANDS_HINT}
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-[var(--text-secondary)]">服務區域（逗號分隔）</span>
                <input
                  value={editForm.regions}
                  onChange={(e) => setEditForm((f) => ({ ...f, regions: e.target.value }))}
                  placeholder="TPE, NTC"
                  className="rounded border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none"
                />
              </label>
            </div>
            {actionMsg && <p className="mt-3 text-[13px] text-red-600">{actionMsg}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setEditOpen(false)}
                disabled={actionBusy}
                className="rounded border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={actionBusy}
                className="rounded bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {actionBusy ? "儲存中…" : "儲存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
