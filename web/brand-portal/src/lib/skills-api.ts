/**
 * skills-api.ts — AI 技能（Skill）熱更新 API client（CR-0167 / LiveSkill）。
 *
 * 對齊 api/routers/skills_v2.py（回 {data, error} 信封；此處統一取 .data）。
 * 路徑帶 /api/v1 前綴（skills_v2 router 掛於 /api/v1，與 config 家族一致）。
 *
 * 角色（後端 role_required 為準；前端僅做 UX gate）：
 *   讀/存草稿＝OPS_ROLES；發佈/回滾＝admin。
 */

import { api } from "@/lib/api";

const BASE = "/api/v1/knowledge-base/skills";

export type SkillStatus = "draft" | "published" | "retired";
export type SkillSource = "brand_edit" | "pipeline_ingest" | "factory_seed";

export interface SkillSummary {
  skill_name: string;
  latest_version: number;
  published_version: number | null;
  latest_status: SkillStatus;
  latest_source: SkillSource;
  updated_at: string | null;
}

export interface SkillDetail {
  skill_name: string;
  version: number;
  files: Record<string, string>;
  status: SkillStatus;
  source: SkillSource;
  note: string | null;
  created_at: string | null;
  published_at: string | null;
}

export interface SkillRevision {
  version: number;
  status: SkillStatus;
  source: SkillSource;
  note: string | null;
  created_by: string | null;
  created_at: string | null;
  published_at: string | null;
}

interface Envelope<T> {
  data: T;
  error: unknown;
}

export async function listSkills(): Promise<SkillSummary[]> {
  const res = await api.get<Envelope<{ items: SkillSummary[] }>>(BASE);
  return res.data.items;
}

export async function getSkill(name: string, version?: number): Promise<SkillDetail> {
  const q = version != null ? `?version=${version}` : "";
  const res = await api.get<Envelope<SkillDetail>>(`${BASE}/${encodeURIComponent(name)}${q}`);
  return res.data;
}

export async function saveDraft(
  name: string,
  files: Record<string, string>,
  note?: string,
): Promise<{ version: number; status: SkillStatus }> {
  const res = await api.put<Envelope<{ version: number; status: SkillStatus }>>(
    `${BASE}/${encodeURIComponent(name)}`,
    { files, note },
  );
  return res.data;
}

export async function publishSkill(
  name: string,
  version: number,
): Promise<{ version: number; published_stamp: number }> {
  const res = await api.post<Envelope<{ version: number; published_stamp: number }>>(
    `${BASE}/${encodeURIComponent(name)}/publish`,
    { version },
  );
  return res.data;
}

export async function listRevisions(name: string): Promise<SkillRevision[]> {
  const res = await api.get<Envelope<{ items: SkillRevision[] }>>(
    `${BASE}/${encodeURIComponent(name)}/revisions`,
  );
  return res.data.items;
}

export async function rollbackSkill(
  name: string,
  targetVersion: number,
): Promise<{ version: number; published_stamp: number }> {
  const res = await api.post<Envelope<{ version: number; published_stamp: number }>>(
    `${BASE}/${encodeURIComponent(name)}/rollback`,
    { target_version: targetVersion },
  );
  return res.data;
}

// ── UI helpers ───────────────────────────────────────────────────────────────

export const STATUS_LABEL: Record<SkillStatus, string> = {
  draft: "草稿",
  published: "發佈中",
  retired: "已封存",
};

export const SOURCE_LABEL: Record<SkillSource, string> = {
  brand_edit: "品牌編輯",
  pipeline_ingest: "自動汲取",
  factory_seed: "出廠範本",
};
