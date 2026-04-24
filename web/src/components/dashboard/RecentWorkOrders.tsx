import StatusBadge from "@/components/ui/StatusBadge";
import type { StatusBadgeProps } from "@/components/ui/StatusBadge";

interface WorkOrder {
  id: string;
  customer: string;
  lockModel: string;
  status: { label: string; variant: StatusBadgeProps["variant"] };
  priority: { label: string; variant: StatusBadgeProps["variant"] };
  createdAt: string;
  technician: string | null;
}

const orders: WorkOrder[] = [
  {
    id: "WO-20260422-0037",
    customer: "陳小姐",
    lockModel: "Yale YDM-4109",
    status: { label: "進行中", variant: "in-progress" },
    priority: { label: "急件", variant: "urgent" },
    createdAt: "25 分鐘前",
    technician: "李師傅",
  },
  {
    id: "WO-20260422-0036",
    customer: "林先生",
    lockModel: "Samsung SHP-DP609",
    status: { label: "已指派", variant: "assigned" },
    priority: { label: "一般", variant: "normal" },
    createdAt: "1 小時前",
    technician: "張師傅",
  },
  {
    id: "WO-20260422-0035",
    customer: "王太太",
    lockModel: "Philips DDL702",
    status: { label: "待指派", variant: "pending" },
    priority: { label: "緊急", variant: "overdue" },
    createdAt: "2 小時前",
    technician: null,
  },
  {
    id: "WO-20260422-0034",
    customer: "張先生",
    lockModel: "Gateman F300",
    status: { label: "已完成", variant: "completed" },
    priority: { label: "一般", variant: "normal" },
    createdAt: "3 小時前",
    technician: "陳師傅",
  },
  {
    id: "WO-20260422-0033",
    customer: "劉小姐",
    lockModel: "Yale YDR-323",
    status: { label: "逾時", variant: "overdue" },
    priority: { label: "急件", variant: "urgent" },
    createdAt: "4 小時前",
    technician: "王師傅",
  },
];

const columns = [
  { key: "id", label: "工單編號", width: "w-[160px]" },
  { key: "customer", label: "客戶名稱", width: "w-[120px]" },
  { key: "lockModel", label: "鎖型型號", width: "w-[180px]" },
  { key: "status", label: "狀態", width: "w-[100px]" },
  { key: "priority", label: "優先度", width: "w-[90px]" },
  { key: "createdAt", label: "建立時間", width: "w-[110px]" },
  { key: "technician", label: "指派技師", width: "flex-1" },
] as const;

export default function RecentWorkOrders() {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex items-center justify-between px-5 py-4">
        <h3 className="text-[18px] font-bold text-[#18181B]">最近工單</h3>
        <button className="text-[14px] font-medium text-[var(--primary)]">
          查看全部 →
        </button>
      </div>

      <div className="flex bg-[#F1F5F9] px-5 py-[10px]">
        {columns.map((col) => (
          <div key={col.key} className={col.width}>
            <span className="text-[12px] font-semibold uppercase tracking-wider text-[#71717A]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {orders.map((order, idx) => (
        <div key={order.id}>
          <div
            className={`flex items-center px-5 py-3 ${
              idx % 2 === 1 ? "bg-[var(--bg-page)]" : "bg-white"
            }`}
          >
            <div className="w-[160px]">
              <span className="text-[13px] font-medium text-[#18181B]">
                {order.id}
              </span>
            </div>
            <div className="w-[120px]">
              <span className="text-[13px] text-[#18181B]">{order.customer}</span>
            </div>
            <div className="w-[180px]">
              <span className="text-[13px] text-[#18181B]">{order.lockModel}</span>
            </div>
            <div className="w-[100px]">
              <StatusBadge
                label={order.status.label}
                variant={order.status.variant}
              />
            </div>
            <div className="w-[90px]">
              <StatusBadge
                label={order.priority.label}
                variant={order.priority.variant}
              />
            </div>
            <div className="w-[110px]">
              <span className="text-[13px] text-[#71717A]">
                {order.createdAt}
              </span>
            </div>
            <div className="flex-1">
              <span className="text-[13px] text-[#18181B]">
                {order.technician ?? (
                  <span className="text-[#A1A1AA]">—</span>
                )}
              </span>
            </div>
          </div>
          {idx < orders.length - 1 && (
            <div className="h-px bg-[#E4E4E7]" />
          )}
        </div>
      ))}

      <div className="h-px bg-[#E4E4E7]" />
      <div className="flex justify-center px-5 py-3">
        <span className="text-[12px] text-[#A1A1AA]">
          顯示最近 5 筆，共 47 筆
        </span>
      </div>
    </div>
  );
}
