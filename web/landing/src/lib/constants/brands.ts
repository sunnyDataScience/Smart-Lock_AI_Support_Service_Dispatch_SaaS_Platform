/**
 * 智慧鎖品牌 — 單一來源 (single source of truth)。
 *
 * 收斂前：admin/customers、register、technicians/[id]、CreateTechnicianModal
 * 各自硬編一份「互不一致」的品牌清單（fix/admin-hardcode-cleanup, 2026-06-28）。
 * 本檔為「客戶設備品牌 / 技師可服務品牌」維度的唯一正典。
 *
 * 正典核心來自產品知識庫 references（bronze 來源，
 * agent/lockcore/skills/locksmith-product-knowledge/references/）：
 *   3E / Chatlock / Dormakaba / Kaadas / Milre(美樂) / Philips
 * 另保留前端既有、但無知識庫背書的真實市場品牌（Yale / Samsung），
 * 避免既有篩選選項回歸（drop 既有選項屬 regression；多列品牌只會讓篩選結果為空，無害）。
 *
 * ⚠️ 不納入本常數的範圍：
 * - knowledge-base/manuals、knowledge-base/cases 的品牌 filter 是「綁定後端已存
 *   品牌字串」的搜尋值，且資料層本身大小寫 / 中英不一致（dormakaba vs Dormakaba、
 *   美樂 vs Milre，另有未列入下拉的 鎖市 / 小島 / Chainlock）。統一其 value 會打到
 *   KB 搜尋結果，屬「資料正規化」問題（需正規化 data/storage 既存 brand metadata），
 *   應另開 CR 於資料層處理，不在前端常數層 paper over。
 * - 品牌 → 徽章配色 map（technicians 列表 BRAND_COLORS）屬顯示樣式，另一關注點。
 */

export interface LockBrand {
  /** 送往後端的值（device_brand 篩選 / 技師 skills 比對）*/
  value: string;
  /** UI 顯示文字（品牌多為專有名，僅 Milre 有常用中文別名 美樂）*/
  label: string;
}

/** 客戶設備品牌 / 技師可服務品牌的正典清單 */
export const LOCK_BRANDS: readonly LockBrand[] = [
  { value: "Yale", label: "Yale" },
  { value: "Dormakaba", label: "Dormakaba" },
  { value: "Philips", label: "Philips" },
  { value: "Kaadas", label: "Kaadas" },
  { value: "Chatlock", label: "Chatlock" },
  { value: "Milre", label: "Milre（美樂）" },
  { value: "3E", label: "3E" },
  { value: "Samsung", label: "Samsung" },
] as const;

/** 逗號分隔的範例品牌字串，給 input placeholder 提示用 */
export const LOCK_BRANDS_HINT = LOCK_BRANDS.slice(0, 3)
  .map((b) => b.value)
  .join(", ");
