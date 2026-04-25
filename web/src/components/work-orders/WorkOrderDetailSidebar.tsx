"use client";

import {
  LockOpen,
  Key,
  Phone,
  MapPin,
  TriangleAlert,
  Clock3,
  Star,
} from "lucide-react";

const skills = ["電子鎖安裝", "指紋模組", "Yale", "Gateman", "+2"];

const priceRows = [
  { label: "工資", value: "NT$ 1,800" },
  { label: "零件費", value: "NT$ 2,500" },
  { label: "出勤費", value: "NT$ 300" },
];

export default function WorkOrderDetailSidebar() {
  return (
    <div className="flex w-[380px] flex-shrink-0 flex-col gap-4 overflow-auto bg-[#F1F5F9] p-5">
      {/* Device Status Panel */}
      <div className="flex flex-col gap-3 rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <div className="flex h-[200px] items-center justify-center rounded-lg bg-[#F8FAFC]">
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-[#E2E8F0]">
            <span className="text-[32px] text-[var(--text-disabled)]">🔒</span>
          </div>
        </div>
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          Yale YDM-4109
        </span>
        <span className="text-[12px] text-[var(--text-secondary)]">
          S/N: YDM4109-2024-A8F3
        </span>

        {/* Metrics Row */}
        <div className="flex gap-2">
          <div className="flex flex-1 flex-col items-center gap-1 rounded-lg bg-[#F8FAFC] p-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full border-[3px] border-[var(--success)]">
              <span className="text-[10px] font-semibold text-[var(--text-primary)]">
                75%
              </span>
            </div>
            <span className="text-[11px] text-[var(--text-secondary)]">
              電量
            </span>
          </div>
          <div className="flex flex-1 flex-col items-center gap-1 rounded-lg bg-[#F8FAFC] p-2">
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded-full bg-[var(--success)]" />
              <span className="text-[12px] font-semibold text-[var(--success)]">
                在線
              </span>
            </div>
            <span className="text-[11px] text-[var(--text-secondary)]">
              連線
            </span>
          </div>
          <div className="flex flex-1 flex-col items-center gap-1 rounded-lg bg-[#F8FAFC] p-2">
            <Clock3 className="h-5 w-5 text-[#64748B]" />
            <span className="text-[12px] text-[var(--text-primary)]">
              15 分鐘前
            </span>
            <span className="text-[11px] text-[var(--text-secondary)]">
              最近操作
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          <button className="flex h-9 items-center justify-center gap-2 rounded-lg bg-[var(--accent)]">
            <LockOpen className="h-4 w-4 text-white" />
            <span className="text-[13px] font-semibold text-white">
              遠端開鎖
            </span>
          </button>
          <button className="flex h-9 items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <Key className="h-4 w-4 text-[var(--text-primary)]" />
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              重置密碼
            </span>
          </button>
        </div>
      </div>

      {/* Customer Info */}
      <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[16px] font-semibold text-[var(--text-primary)]">
          客戶資訊
        </span>
        <span className="text-[14px] font-semibold text-[var(--text-primary)]">
          陳小姐
        </span>
        <div className="flex items-center gap-[6px]">
          <Phone className="h-[14px] w-[14px] text-[var(--primary)]" />
          <span className="text-[14px] text-[var(--primary)]">
            0912-345-678
          </span>
        </div>
        <div className="flex gap-[6px]">
          <MapPin className="mt-[2px] h-[14px] w-[14px] flex-shrink-0 text-[var(--primary)]" />
          <span className="text-[13px] text-[var(--primary)]">
            台北市大安區忠孝東路四段100號12F
          </span>
        </div>
        <span className="inline-flex w-fit rounded bg-[#FEF3C7] px-2 py-[2px] text-[11px] font-semibold text-[#92400E]">
          VIP
        </span>
        <span className="text-[13px] font-medium text-[var(--primary)]">
          查看歷史工單 (5 筆) →
        </span>
      </div>

      {/* Technician Info */}
      <div className="flex flex-col gap-[10px] rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[16px] font-semibold text-[var(--text-primary)]">
          指派技師
        </span>
        <div className="flex items-center gap-[10px]">
          <div className="h-10 w-10 flex-shrink-0 rounded-full bg-[#CBD5E1]" />
          <div className="flex flex-col gap-[2px]">
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              李建宏
            </span>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((i) => (
                <Star
                  key={i}
                  className="h-[14px] w-[14px] fill-[var(--accent)] text-[var(--accent)]"
                />
              ))}
              <span className="text-[12px] text-[var(--text-secondary)]">
                4.8/5.0 (127 則評價)
              </span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-[6px]">
          {skills.map((s) => (
            <span
              key={s}
              className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[12px] text-[#334155]"
            >
              {s}
            </span>
          ))}
        </div>
        <div className="relative h-[100px] overflow-hidden rounded-lg bg-[#E2E8F0]">
          <div className="absolute left-[90px] top-[40px] h-3 w-3 rounded-full border-2 border-white bg-[var(--primary)]" />
          <div className="absolute left-[200px] top-[55px] h-3 w-3 rounded-full border-2 border-white bg-[var(--error)]" />
          <span className="absolute left-[70px] top-[26px] text-[9px] font-semibold text-[var(--primary)]">
            技師
          </span>
          <span className="absolute left-[185px] top-[70px] text-[9px] font-semibold text-[var(--error)]">
            工單
          </span>
        </div>
        <span className="text-[12px] text-[var(--text-secondary)]">
          距離工單地址 3.2 km
        </span>
        <button className="flex h-[34px] items-center justify-center gap-[6px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)]">
          <Phone className="h-[14px] w-[14px] text-[var(--text-primary)]" />
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            聯繫技師
          </span>
        </button>
      </div>

      {/* Quotation */}
      <div className="flex flex-col gap-2 rounded-lg bg-[var(--bg-surface)] p-4 shadow-sm">
        <span className="text-[16px] font-semibold text-[var(--text-primary)]">
          報價明細
        </span>
        {priceRows.map((r) => (
          <div key={r.label} className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-primary)]">
              {r.label}
            </span>
            <span className="font-mono text-[13px] text-[var(--text-primary)]">
              {r.value}
            </span>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--error)]">折扣</span>
          <span className="font-mono text-[13px] text-[var(--error)]">
            -NT$ 200
          </span>
        </div>
        <div className="h-px w-full bg-[var(--border)]" />
        <div className="flex items-center justify-between">
          <span className="text-[14px] font-bold text-[var(--text-primary)]">
            合計
          </span>
          <span className="font-mono text-[16px] font-bold text-[var(--text-primary)]">
            NT$ 4,400
          </span>
        </div>
        <span className="inline-flex w-fit rounded bg-[#D1FAE5] px-2 py-[2px] text-[11px] font-semibold text-[#047857]">
          已付款
        </span>
        <span className="text-[12px] text-[var(--text-secondary)]">
          付款方式：信用卡
        </span>
        <span className="text-[13px] text-[var(--primary)]">查看發票 →</span>
      </div>

      {/* Action Panel */}
      <div className="flex flex-col gap-2 rounded-lg border-t-2 border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <button className="flex h-10 items-center justify-center gap-2 rounded-lg bg-[var(--accent)]">
          <TriangleAlert className="h-4 w-4 text-white" />
          <span className="text-[14px] font-semibold text-white">標記異常</span>
        </button>
        <span className="text-center text-[13px] text-[var(--text-secondary)]">
          技師正在現場作業中
        </span>
      </div>
    </div>
  );
}
