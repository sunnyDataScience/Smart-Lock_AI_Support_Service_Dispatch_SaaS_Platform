import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import Skeleton from "@/components/ui/Skeleton";

/**
 * /dashboard 路由 navigation 時的 fallback skeleton。
 * Next.js App Router 在 client-side navigation 期間自動掛載此元件，
 * 直到 page.tsx 的 chunk 載完才切換。
 *
 * 給 user 的視覺感受：點擊「儀表板」立即看到結構而不是白屏。
 */
export default function DashboardLoading() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title="儀表板" subtitle="近 7 日營運概況" />
        <main className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {/* 4 KPI cards (top row) */}
          <div className="flex gap-6">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height="h-[120px]" rounded="lg" className="flex-1" />
            ))}
          </div>
          {/* 2 KPI cards (mid row) */}
          <div className="flex gap-6">
            {[0, 1].map((i) => (
              <Skeleton key={i} height="h-[120px]" rounded="lg" className="flex-1" />
            ))}
          </div>
          {/* Hot topics + brands */}
          <div className="flex gap-6">
            <Skeleton height="h-[180px]" rounded="lg" className="flex-1" />
            <Skeleton height="h-[180px]" rounded="lg" className="flex-1" />
          </div>
          {/* Trend chart + technician status */}
          <div className="flex gap-6">
            <Skeleton height="h-[360px]" rounded="lg" className="w-[741px]" />
            <Skeleton height="h-[360px]" rounded="lg" className="w-[371px]" />
          </div>
          {/* Recent work orders table */}
          <Skeleton height="h-[280px]" rounded="lg" />
        </main>
      </div>
    </div>
  );
}
