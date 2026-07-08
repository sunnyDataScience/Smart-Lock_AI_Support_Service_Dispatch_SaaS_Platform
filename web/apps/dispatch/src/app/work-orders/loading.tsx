import Sidebar from "@shared/components/layout/Sidebar";
import Header from "@shared/components/layout/Header";
import Skeleton, { SkeletonTableRow } from "@shared/components/ui/Skeleton";

export default function WorkOrdersLoading() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header title="派工管理" subtitle="工單列表與檢視切換" />
        <main className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
          {/* Filter / view-toggle bar */}
          <div className="flex items-center justify-between">
            <Skeleton height="h-9" width="w-[320px]" rounded="md" />
            <Skeleton height="h-9" width="w-[200px]" rounded="md" />
          </div>
          {/* Table header + rows */}
          <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <SkeletonTableRow cols={7} />
            {Array.from({ length: 8 }).map((_, i) => (
              <SkeletonTableRow key={i} cols={7} />
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
