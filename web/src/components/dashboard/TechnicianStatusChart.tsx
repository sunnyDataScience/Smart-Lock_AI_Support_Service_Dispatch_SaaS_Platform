"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

const data = [
  { name: "在線空閒", value: 3, color: "#10B981" },
  { name: "執行中", value: 5, color: "#2563EB" },
  { name: "離線", value: 2, color: "#A1A1AA" },
  { name: "請假", value: 2, color: "#F59E0B" },
];

const total = data.reduce((sum, d) => sum + d.value, 0);

export default function TechnicianStatusChart() {
  return (
    <div className="flex w-[371px] flex-col gap-4 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-6">
      <h3 className="text-[20px] font-semibold text-[#18181B]">技師狀態分佈</h3>

      <div className="relative mx-auto h-[168px] w-[168px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={80}
              startAngle={90}
              endAngle={-270}
              paddingAngle={0}
              dataKey="value"
              stroke="none"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[32px] font-bold leading-none text-[#18181B]">
            {total}
          </span>
          <span className="text-[12px] font-medium text-[#A1A1AA]">總人數</span>
        </div>
      </div>

      <div className="flex flex-col gap-[10px]">
        {data.map((item) => (
          <div key={item.name} className="flex items-center gap-2">
            <div
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[13px] font-medium text-[#71717A]">
              {item.name}
            </span>
            <span className="text-[13px] font-semibold text-[#18181B]">
              {item.value}人
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
