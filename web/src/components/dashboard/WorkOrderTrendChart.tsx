"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useState } from "react";

const data = [
  { date: "4/9", created: 28, completed: 22 },
  { date: "4/10", created: 32, completed: 25 },
  { date: "4/11", created: 30, completed: 28 },
  { date: "4/12", created: 25, completed: 24 },
  { date: "4/13", created: 35, completed: 30 },
  { date: "4/14", created: 38, completed: 32 },
  { date: "4/15", created: 33, completed: 31 },
  { date: "4/16", created: 36, completed: 33 },
  { date: "4/17", created: 40, completed: 35 },
  { date: "4/18", created: 42, completed: 38 },
  { date: "4/19", created: 38, completed: 36 },
  { date: "4/20", created: 44, completed: 40 },
  { date: "4/21", created: 45, completed: 42 },
  { date: "4/22", created: 47, completed: 43 },
];

const ranges = ["7天", "14天", "30天"] as const;

export default function WorkOrderTrendChart() {
  const [activeRange, setActiveRange] = useState<(typeof ranges)[number]>("14天");

  return (
    <div className="flex w-[741px] flex-col gap-4 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <h3 className="text-[20px] font-semibold text-[#18181B]">工單趨勢</h3>
        <div className="flex gap-0 rounded-lg bg-[#F4F4F5] p-1">
          {ranges.map((range) => (
            <button
              key={range}
              onClick={() => setActiveRange(range)}
              className={`rounded-md px-3 py-[6px] text-[12px] font-medium ${
                activeRange === range
                  ? "bg-[var(--primary)] text-white"
                  : "text-[#71717A]"
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      <div className="h-[240px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="0" stroke="#F4F4F5" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "#A1A1AA" }}
              axisLine={{ stroke: "#E4E4E7" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#A1A1AA" }}
              axisLine={false}
              tickLine={false}
              domain={[0, 50]}
              ticks={[0, 10, 20, 30, 40, 50]}
            />
            <Tooltip />
            <defs>
              <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2563EB" stopOpacity={0.19} />
                <stop offset="100%" stopColor="#2563EB" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10B981" stopOpacity={0.19} />
                <stop offset="100%" stopColor="#10B981" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="created"
              stroke="#2563EB"
              strokeWidth={2.5}
              fill="url(#blueGrad)"
              name="新建工單"
            />
            <Area
              type="monotone"
              dataKey="completed"
              stroke="#10B981"
              strokeWidth={2.5}
              fill="url(#greenGrad)"
              name="已完成工單"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-center gap-6">
        <div className="flex items-center gap-[6px]">
          <div className="h-2 w-2 rounded-full bg-[#2563EB]" />
          <span className="text-[13px] font-medium text-[#71717A]">新建工單</span>
        </div>
        <div className="flex items-center gap-[6px]">
          <div className="h-2 w-2 rounded-full bg-[#10B981]" />
          <span className="text-[13px] font-medium text-[#71717A]">已完成工單</span>
        </div>
      </div>
    </div>
  );
}
