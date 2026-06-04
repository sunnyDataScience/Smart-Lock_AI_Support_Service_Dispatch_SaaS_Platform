/**
 * KB shape adapter — 把 v2 `KBDocument`（meta-wrap，CR-0005 HD-01=a）
 * 對應成 UI 既有期望的 `CaseEntry` flat shape，避免每個 page 都要改 JSX。
 *
 * 業主決策來源：docs/_audit/CR-0005-kb-v2-expand-and-shape.md §8 HD-01 = (a)
 *
 * v2 KBDocument shape（api/routers/kb_v2.py:_case_to_kb_document）：
 *   {
 *     id, doc_type: 'case', title,
 *     tenant_scope, brand_scope: [string], project_scope,
 *     version, effective_date,
 *     meta: { problem_description, solution, brand, model, tags,
 *             verified, embedding_status, created_at, updated_at }
 *   }
 *
 * 既有 UI 期望（components.schemas.CaseEntry）：
 *   { id, title, problem_description, solution, brand, model?, tags?,
 *     verified, embedding_status, created_at, updated_at }
 */

import type { components } from "@/types/api.generated";

type CaseEntry = components["schemas"]["CaseEntry"];

/** v2 KBDocument shape（inline，沒 export 給 generated.ts）。 */
export interface KBDocument {
  id: string;
  doc_type: "case" | "manual";
  title?: string;
  tenant_scope?: unknown[];
  brand_scope?: string[];
  project_scope?: unknown[];
  version?: string | null;
  effective_date?: string | null;
  meta?: {
    problem_description?: string;
    solution?: string;
    brand?: string;
    model?: string;
    tags?: string[];
    verified?: boolean;
    embedding_status?: "processing" | "ready" | "failed";
    created_at?: string;
    updated_at?: string;
  };
}

/**
 * KBDocument (case doc_type) → CaseEntry flat shape。
 *
 * meta 內欄位拉到頂層；brand_scope[0] → brand；缺值給安全 default。
 * 不適用於 doc_type='manual'（caller 自己判斷）。
 */
export function kbDocumentToCaseEntry(doc: KBDocument): CaseEntry {
  const m = doc.meta ?? {};
  return {
    id: doc.id,
    title: doc.title ?? "",
    problem_description: m.problem_description ?? "",
    solution: m.solution ?? "",
    brand: m.brand ?? (doc.brand_scope?.[0] ?? ""),
    model: m.model,
    tags: m.tags,
    verified: m.verified ?? false,
    embedding_status: m.embedding_status ?? "processing",
    created_at: m.created_at ?? "",
    updated_at: m.updated_at ?? "",
  };
}
