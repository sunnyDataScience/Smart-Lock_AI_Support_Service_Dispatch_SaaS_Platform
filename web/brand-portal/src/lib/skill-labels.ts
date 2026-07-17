/**
 * AI 技能顯示層口語化(20260715 會議 #10,業主拍板「顯示層口語化」方案)。
 *
 * 原則:skill 與檔案的**儲存結構原封不動**(Agent Skills 標準可攜性、LiveSkill
 * 物化皆不受影響),只在 UI 加一層人話——消費者(品牌方小編)看「客服話術 SOP」,
 * 工程看得到機器名小字。未知 skill(品牌自建)fallback 原名。
 */

export const SKILL_FRIENDLY: Record<string, { title: string; desc: string }> = {
  "locksmith-cs-sop": {
    title: "客服話術 SOP",
    desc: "接單路由・轉真人・派工判斷・紅線規則",
  },
  "locksmith-product-knowledge": {
    title: "產品知識庫",
    desc: "品牌型號事實・規格・常見問答",
  },
};

export function skillTitle(name: string): string {
  return SKILL_FRIENDLY[name]?.title ?? name;
}

export function skillDesc(name: string): string | null {
  return SKILL_FRIENDLY[name]?.desc ?? null;
}

/**
 * 從 markdown 內容抽第一個標題當口語名(略過 YAML frontmatter);
 * 抽不到 fallback。參考文件列表用:「預約安裝流程」而非 booking.md。
 */
export function mdTitle(content: string | undefined, fallback: string): string {
  if (!content) return fallback;
  let body = content;
  if (body.startsWith("---")) {
    const end = body.indexOf("\n---", 3);
    if (end !== -1) body = body.slice(end + 4);
  }
  for (const line of body.split("\n").slice(0, 30)) {
    const m = line.match(/^#{1,3}\s+(.+?)\s*$/);
    if (m) return m[1];
  }
  return fallback;
}
