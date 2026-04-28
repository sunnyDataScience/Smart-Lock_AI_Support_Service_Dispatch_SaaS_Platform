"use client";

const data = [
  { name: "維修服務", value: "NT$ 520,000", width: "65%", color: "#2563EB", trackBg: "#EFF6FF" },
  { name: "清潔服務", value: "NT$ 380,000", width: "50%", color: "#F59E0B", trackBg: "#FFF7ED" },
  { name: "安裝服務", value: "NT$ 240,000", width: "35%", color: "#10B981", trackBg: "#ECFDF5" },
  { name: "諮詢服務", value: "NT$ 144,500", width: "22%", color: "#8B5CF6", trackBg: "#F5F3FF" },
];

export default function ServiceTypeChart() {
  return (
    <div className="flex flex-1 flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center gap-2">
        <span className="text-base font-semibold text-[var(--text-primary)]">
          服務類型營收分佈
        </span>
        <span className="rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
          示意（待 invoice category 欄位上線）
        </span>
      </div>

      <div className="flex flex-1 flex-col justify-center gap-[14px]">
        {data.map((row) => (
          <div key={row.name} className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-[var(--text-primary)]">
                {row.name}
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {row.value}
              </span>
            </div>
            <div
              className="h-5 w-full rounded"
              style={{ backgroundColor: row.trackBg }}
            >
              <div
                className="h-5 rounded"
                style={{ width: row.width, backgroundColor: row.color }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
