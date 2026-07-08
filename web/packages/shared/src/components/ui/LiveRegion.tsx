/**
 * LiveRegion — 視覺隱藏的 ARIA live region，給 screen reader 公告動態狀態
 *
 * 用途：fetch 完成、表格更新、無障礙級狀態變化時，讓 screen reader 即時念出。
 *
 * WCAG 4.1.3 Status Messages — 動態狀態（loading/success/error）必須能被
 * assistive technology 感知，沒手動觸發 focus 也行。
 *
 * Variants:
 *   politeness="polite"   ≈ 等使用者閒下來才念（預設，狀態更新用）
 *   politeness="assertive" ≈ 立即打斷念（錯誤訊息用，role="alert" 已經是這個）
 *
 * 用法：
 *   <LiveRegion>{loading ? "載入中" : `已載入 ${total} 筆`}</LiveRegion>
 *   {error && <LiveRegion politeness="assertive">{error}</LiveRegion>}
 */

interface Props {
  children: React.ReactNode;
  politeness?: "polite" | "assertive";
  /** 完整原子內容變動才念（預設 true，避免片段念到一半被替換） */
  atomic?: boolean;
  /** 把整個 region 隱藏（給 screen reader 用，不顯示給視覺） */
  visuallyHidden?: boolean;
  className?: string;
}

export default function LiveRegion({
  children,
  politeness = "polite",
  atomic = true,
  visuallyHidden = true,
  className = "",
}: Props) {
  return (
    <div
      role="status"
      aria-live={politeness}
      aria-atomic={atomic}
      className={`${visuallyHidden ? "sr-only" : ""} ${className}`}
    >
      {children}
    </div>
  );
}
