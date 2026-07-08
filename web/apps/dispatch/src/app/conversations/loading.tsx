import Sidebar from "@shared/components/layout/Sidebar";
import Header from "@shared/components/layout/Header";
import Skeleton, { SkeletonTableRow } from "@shared/components/ui/Skeleton";

export default function ConversationsLoading() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header title="對話管理" subtitle="客戶對話列表" />
        <main className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
          {/* Tabs */}
          <div className="flex gap-3">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height="h-8" width="w-20" rounded="md" />
            ))}
          </div>
          {/* Table */}
          <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <SkeletonTableRow cols={6} />
            {Array.from({ length: 8 }).map((_, i) => (
              <SkeletonTableRow key={i} cols={6} />
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
