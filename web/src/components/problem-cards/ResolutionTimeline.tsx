"use client";

interface TimelineStep {
  level: string;
  dotColor: string;
  confidence: string;
  confidenceColor: string;
  confidenceBg: string;
  time: string;
  description: string;
}

const steps: TimelineStep[] = [
  {
    level: "L1",
    dotColor: "#2563EB",
    confidence: "45%",
    confidenceColor: "#DC2626",
    confidenceBg: "#FEE2E2",
    time: "2026-04-22 14:25",
    description: "建議客戶重設密碼並更換電池",
  },
  {
    level: "L2",
    dotColor: "#6366F1",
    confidence: "78%",
    confidenceColor: "#92400E",
    confidenceBg: "#FEF3C7",
    time: "2026-04-22 14:30",
    description: "遠端診斷離合器模組訊號，判斷機械故障",
  },
  {
    level: "L3",
    dotColor: "#EF4444",
    confidence: "92%",
    confidenceColor: "#166534",
    confidenceBg: "#DCFCE7",
    time: "2026-04-22 14:35",
    description: "需安排技師現場更換離合器組件",
  },
];

export default function ResolutionTimeline() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
        解決嘗試歷程
      </h2>

      <div className="flex flex-col pt-4">
        {steps.map((step, i) => (
          <div key={step.level}>
            <div className="flex gap-4">
              <div
                className="mt-[3px] h-[14px] w-[14px] flex-shrink-0 rounded-full"
                style={{ backgroundColor: step.dotColor }}
              />
              <div className="flex w-full flex-col gap-[6px]">
                <div className="flex w-full items-center gap-2">
                  <span className="text-[14px] font-bold text-[var(--text-primary)]">
                    {step.level}
                  </span>
                  <span
                    className="rounded-[10px] px-2 py-[2px] text-[12px] font-semibold"
                    style={{
                      color: step.confidenceColor,
                      backgroundColor: step.confidenceBg,
                    }}
                  >
                    {step.confidence}
                  </span>
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {step.time}
                  </span>
                </div>
                <p className="text-[14px] text-[var(--text-primary)]">
                  {step.description}
                </p>
              </div>
            </div>

            {i < steps.length - 1 && (
              <div className="py-1 pl-[30px]">
                <div className="border-l-2 border-[var(--text-disabled)] py-1 pl-4">
                  <div className="h-2" />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
