"use client";

import {
  CircleAlert,
  Wrench,
  Check,
  TriangleAlert,
  User,
  X,
  UserPlus,
} from "lucide-react";

interface MapPin {
  icon: React.ElementType;
  color: string;
  size: number;
  x: number;
  y: number;
  label?: string;
}

const pins: MapPin[] = [
  { icon: CircleAlert, color: "#EF4444", size: 32, x: 120, y: 180 },
  { icon: Wrench, color: "#3B82F6", size: 32, x: 280, y: 120 },
  { icon: Check, color: "#10B981", size: 32, x: 450, y: 280 },
  { icon: TriangleAlert, color: "#F59E0B", size: 32, x: 350, y: 400 },
  { icon: CircleAlert, color: "#EF4444", size: 32, x: 550, y: 160 },
  { icon: User, color: "#2563EB", size: 36, x: 200, y: 250 },
  { icon: User, color: "#2563EB", size: 36, x: 500, y: 350 },
  { icon: Wrench, color: "#3B82F6", size: 32, x: 650, y: 420 },
];

interface MapViewProps {
  onAssign?: (workOrderId: string) => void;
}

export default function MapView({ onAssign }: MapViewProps) {
  return (
    <div className="relative flex-1 bg-[#C8D6E5]">
      {/* Map placeholder background */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#D1D8E0] to-[#ABB7C4]">
        {/* Grid lines to simulate map */}
        <div className="absolute inset-0 opacity-20">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={`h${i}`}
              className="absolute left-0 right-0 border-t border-[#94A3B8]"
              style={{ top: `${(i + 1) * 8}%` }}
            />
          ))}
          {Array.from({ length: 16 }).map((_, i) => (
            <div
              key={`v${i}`}
              className="absolute bottom-0 top-0 border-l border-[#94A3B8]"
              style={{ left: `${(i + 1) * 6}%` }}
            />
          ))}
        </div>
      </div>

      {/* Map Pins */}
      {pins.map((pin, i) => (
        <div
          key={i}
          className="absolute flex items-center justify-center rounded-full shadow-lg"
          style={{
            width: pin.size,
            height: pin.size,
            left: pin.x,
            top: pin.y,
            backgroundColor: pin.color,
            border: "2px solid white",
          }}
        >
          <pin.icon className="text-white" style={{ width: pin.size === 36 ? 18 : 16, height: pin.size === 36 ? 18 : 16 }} />
        </div>
      ))}

      {/* Cluster Marker */}
      <div
        className="absolute flex h-11 w-11 items-center justify-center rounded-full bg-[#1E293B] shadow-xl"
        style={{ left: 700, top: 200, border: "3px solid white" }}
      >
        <span className="text-[16px] font-bold text-white">8</span>
      </div>

      {/* Map Popup */}
      <div
        className="absolute flex w-[300px] flex-col gap-3 rounded-xl bg-[var(--bg-surface)] p-4 shadow-xl"
        style={{ left: 60, top: 50 }}
      >
        <div className="flex items-center justify-between">
          <span className="font-mono text-[13px] font-semibold text-[var(--text-primary)]">
            WO-20260422-0001
          </span>
          <X className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
        </div>

        <span className="inline-flex w-fit items-center rounded-full bg-[#6366F1] px-[10px] text-[11px] font-medium leading-[22px] text-white">
          已建立
        </span>

        <div className="h-px w-full bg-[var(--border)]" />

        <div className="flex flex-col gap-[6px]">
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            陳小姐
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            台北市大安區忠孝東路四段100號12F
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            Yale YDM-4109
          </span>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-[6px]">
              <div className="h-5 w-5 rounded-full border border-[var(--text-disabled)]" />
              <span className="text-[12px] text-[var(--text-disabled)]">
                未指派
              </span>
            </div>
            <span className="text-[12px] text-[var(--text-secondary)]">
              剩餘 02:45
            </span>
          </div>
        </div>

        <div className="h-px w-full bg-[var(--border)]" />

        <div className="flex items-center justify-between">
          <button
            className="flex h-[34px] items-center gap-[6px] rounded-lg bg-[var(--primary)] px-4"
            onClick={() => onAssign?.("WO-20260422-0001")}
          >
            <UserPlus className="h-[14px] w-[14px] text-white" />
            <span className="text-[13px] font-semibold text-white">
              指派技師
            </span>
          </button>
          <span className="text-[13px] font-medium text-[var(--primary)]">
            查看詳情 →
          </span>
        </div>
      </div>
    </div>
  );
}
