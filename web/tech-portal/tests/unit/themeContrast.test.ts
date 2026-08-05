/**
 * 師傅站主題對比度回歸測試（2026-07-31）。
 *
 * 背景：業主回報「師傅站卡片背景色跟文字顏色太像」。用瀏覽器逐節點量測後發現
 * 深色模式多處低於 WCAG AA——最嚴重的是 teal 文字鋪在 teal 底上只有 2.97:1。
 *
 * 為什麼寫成「解析 globals.css 算對比」而不是端到端 a11y 測試：
 *   - 這類劣化的**根因幾乎都在 token 定義**（某人調了一個 --primary 就全站受影響），
 *     在 token 層擋住最便宜也最準。
 *   - 不需要瀏覽器 / 不需要跑起服務，任何人改 globals.css 都會立刻被擋。
 *
 * 它擋不住什麼（誠實說明邊界）：元件裡新硬編的顏色（如 text-[#059669]）不在
 * token 層，這裡看不到。那類要靠 code review 或瀏覽器稽核。
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, "../../src/app/globals.css"), "utf8");

/** 取出某個 CSS 區塊（以 selector 開頭到第一個 `}`）內的自訂屬性。 */
function tokensIn(selector: string): Record<string, string> {
  const start = css.indexOf(selector + " {");
  if (start === -1) throw new Error(`globals.css 找不到區塊：${selector}`);
  const end = css.indexOf("\n}", start);
  const block = css.slice(start, end);
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/(--[\w-]+):\s*([^;]+);/g)) {
    out[m[1]] = m[2].trim();
  }
  return out;
}

function toRgb(color: string): [number, number, number, number] {
  const hex = color.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const rgba = color.match(
    /rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+))?\s*\)/,
  );
  if (rgba) {
    return [+rgba[1], +rgba[2], +rgba[3], rgba[4] === undefined ? 1 : +rgba[4]];
  }
  throw new Error(`看不懂的顏色：${color}`);
}

/** 半透明色疊在不透明底色上的實際顏色（--primary-light 在深色模式是 16% teal）。 */
function flatten(fg: string, bg: string): [number, number, number, number] {
  const f = toRgb(fg);
  const b = toRgb(bg);
  const a = f[3];
  return [
    f[0] * a + b[0] * (1 - a),
    f[1] * a + b[1] * (1 - a),
    f[2] * a + b[2] * (1 - a),
    1,
  ];
}

function luminance([r, g, b]: [number, number, number, number]): number {
  const ch = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
}

function contrast(fg: string, bg: string): number {
  const l1 = luminance(toRgb(fg));
  const l2 = luminance(toRgb(bg));
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

const AA_BODY = 4.5;
/** 金額文字專用門檻——見 19_Test_Plan.md:199「金額文字升級 7:1」（NFR-A11y-002）。 */
const AA_MONEY = 7;

const root = tokensIn(":root");
const dark = tokensIn('[data-theme="dark"]');
const soft = tokensIn(".tech-soft");
const softDark = tokensIn('[data-theme="dark"] .tech-soft');

/** 深色模式下師傅站實際生效的值：先 root、再 dark、再 .tech-soft、最後 dark .tech-soft。 */
const darkEffective = { ...root, ...dark, ...soft, ...softDark };
const lightEffective = { ...root, ...soft };

describe("師傅站語意彩字（金額 / 完成 / 待補）對比度", () => {
  const cases: Array<[string, string]> = [
    ["--text-money", "金額"],
    ["--text-success", "已完成"],
    ["--text-warning", "待補齊"],
  ];

  it.each(cases)("%s（%s）淺色模式鋪在白底 / 頁底都要過 AA", (token) => {
    for (const bg of ["#FFFFFF", lightEffective["--bg-page"]]) {
      expect(contrast(lightEffective[token], bg)).toBeGreaterThanOrEqual(AA_BODY);
    }
  });

  it.each(cases)("%s（%s）深色模式鋪在卡片底 / 頁底都要過 AA", (token) => {
    for (const bg of [darkEffective["--bg-surface"], darkEffective["--bg-page"]]) {
      expect(contrast(darkEffective[token], bg)).toBeGreaterThanOrEqual(AA_BODY);
    }
  });

  // 金額文字的門檻比一般本文高 —— 業主正典
  // smartlock-docs/enterprise/19_Test_Plan.md:199：「對比 ≥ 4.5:1
  //（**金額文字升級 7:1**）」，對應 NFR-A11y-002 / TC-A11Y-02。
  // 上面兩支只驗 AA_BODY=4.5，所以 --text-money 長期停在 5.48 也一直是綠的，
  // 靜態走查（2026-08-03 TC-A11Y-02）才發現門檻根本沒被守。
  it("--text-money（金額）淺色模式需達 7:1，比一般本文更嚴", () => {
    for (const bg of ["#FFFFFF", lightEffective["--bg-page"]]) {
      expect(contrast(lightEffective["--text-money"], bg)).toBeGreaterThanOrEqual(
        AA_MONEY,
      );
    }
  });

  it("--text-money（金額）深色模式需達 7:1", () => {
    for (const bg of [darkEffective["--bg-surface"], darkEffective["--bg-page"]]) {
      expect(contrast(darkEffective["--text-money"], bg)).toBeGreaterThanOrEqual(
        AA_MONEY,
      );
    }
  });
});

describe("師傅站主色（--primary）兩種用途都要可讀", () => {
  it("當文字：鋪在 --primary-light 色塊上（原本 2.97:1 的那一處）", () => {
    const tint = flatten(
      softDark["--primary-light"],
      darkEffective["--bg-surface"],
    );
    const tintHex =
      "#" +
      tint
        .slice(0, 3)
        .map((v) => Math.round(v).toString(16).padStart(2, "0"))
        .join("");
    expect(contrast(darkEffective["--primary"], tintHex)).toBeGreaterThanOrEqual(
      AA_BODY,
    );
  });

  it("當文字：鋪在卡片底與頁底", () => {
    for (const bg of [darkEffective["--bg-surface"], darkEffective["--bg-page"]]) {
      expect(contrast(darkEffective["--primary"], bg)).toBeGreaterThanOrEqual(
        AA_BODY,
      );
    }
    expect(
      contrast(lightEffective["--primary"], lightEffective["--bg-page"]),
    ).toBeGreaterThanOrEqual(AA_BODY);
  });

  it("當實心填色：深色模式改配深墨，白字會不可讀（1.9:1）", () => {
    // globals.css 用 class 補丁把 bg-[var(--primary)] 的字改成這個墨色
    const INK = "#04262A";
    expect(css).toContain(INK);
    expect(contrast(INK, darkEffective["--primary"])).toBeGreaterThanOrEqual(
      AA_BODY,
    );
    expect(contrast(INK, softDark["--primary-hover"])).toBeGreaterThanOrEqual(
      AA_BODY,
    );
    // 反向：證明「白字」確實不行，所以上面那條補丁是必要的而非裝飾
    expect(contrast("#FFFFFF", darkEffective["--primary"])).toBeLessThan(AA_BODY);
  });

  it("淺色模式實心填色仍配白字", () => {
    expect(
      contrast("#FFFFFF", lightEffective["--primary"]),
    ).toBeGreaterThanOrEqual(AA_BODY);
  });
});

describe("次要 / 三級文字", () => {
  it("--text-secondary 在明暗兩種頁底、卡片底、灰膠囊上都要過 AA", () => {
    expect(
      contrast(lightEffective["--text-secondary"], lightEffective["--bg-page"]),
    ).toBeGreaterThanOrEqual(AA_BODY);
    expect(
      contrast(
        lightEffective["--text-secondary"],
        lightEffective["--surface-strong"],
      ),
    ).toBeGreaterThanOrEqual(AA_BODY);
    for (const bg of [
      darkEffective["--bg-surface"],
      darkEffective["--bg-page"],
      darkEffective["--surface-strong"],
    ]) {
      expect(
        contrast(darkEffective["--text-secondary"], bg),
      ).toBeGreaterThanOrEqual(AA_BODY);
    }
  });

  it("--text-disabled / --text-tertiary 也是給人讀的（工單編號、時間戳）", () => {
    for (const token of ["--text-disabled", "--text-tertiary"]) {
      expect(
        contrast(darkEffective[token], darkEffective["--bg-surface"]),
      ).toBeGreaterThanOrEqual(AA_BODY);
      expect(
        contrast(lightEffective[token], "#FFFFFF"),
      ).toBeGreaterThanOrEqual(AA_BODY);
    }
  });
});
