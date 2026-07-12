"use client";

import { useEffect, useState } from "react";
import { api, tenantPath } from "@/lib/api";

export interface KbCounts {
  cases: number | undefined;
  manuals: number | undefined;
  sopDrafts: number | undefined;
  skills: number | undefined;
}

/**
 * 知識庫三個分頁（案例 / 手冊 / SOP 草稿）的真實總筆數，供分頁 badge 顯示。
 *
 * 收斂前：cases/manuals/sop-drafts 三頁各自把「別的分頁」count 寫死（128/23/7/6，
 * 且跨頁互相矛盾）。改為各以 limit=1 輕量請求讀後端 total_count
 * （case_service/manual_service/sop_draft_service 已補 COUNT(*)）。
 *
 * 顯示「區段總數」語意（不隨品牌篩選變動），取不到時回 undefined（呼叫端退回 "—"）。
 */
export function useKbCounts(): KbCounts {
  const [counts, setCounts] = useState<KbCounts>({
    cases: undefined,
    manuals: undefined,
    sopDrafts: undefined,
    skills: undefined,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const read = async (path: string): Promise<number | undefined> => {
        try {
          const res = await api.get<{ total_count?: number }>(path);
          return typeof res.total_count === "number" ? res.total_count : undefined;
        } catch {
          return undefined; // 取不到不阻斷頁面，badge 退回 "—"
        }
      };
      // skills 端點回 {data:{items}} 無 total_count → 另讀並取 items 長度
      const readSkills = async (): Promise<number | undefined> => {
        try {
          const res = await api.get<{ data?: { items?: unknown[] } }>(
            "/api/v1/knowledge-base/skills",
          );
          return Array.isArray(res.data?.items) ? res.data!.items!.length : undefined;
        } catch {
          return undefined;
        }
      };
      const [cases, manuals, sopDrafts, skills] = await Promise.all([
        read("/kb/documents?doc_type=case&limit=1"),
        read("/kb/documents?doc_type=manual&limit=1"),
        read(`${tenantPath("/sops/drafts")}?limit=1`),
        readSkills(),
      ]);
      if (!cancelled) setCounts({ cases, manuals, sopDrafts, skills });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return counts;
}
