import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({ baseDirectory: __dirname });

/**
 * ESLint flat config（ESLint 9 + Next 15）。
 *
 * WHY：本站原本宣告了 `npm run lint` 卻**沒有任何 ESLint 設定與依賴** —— `next lint`
 * 會跳互動式設定提問並卡住，等於前端從未真正 lint 過（CI 亦未跑）。此檔補上可執行的
 * 基線設定，四站一致。
 *
 * 規則取捨：採 next/core-web-vitals + next/typescript 官方預設；把「既有程式碼大量命中、
 * 但非執行期缺陷」的規則降為 warn，讓 lint 能以退出碼 0 當 CI gate，同時持續曝光技術債。
 */
const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "out/**",
      "coverage/**",
      "playwright-report/**",
      "test-results/**",
      "src/types/api.generated.ts", // OpenAPI 產生檔，不手改
      "next-env.d.ts", // Next 自動產生；其 triple-slash reference 為必要寫法，非缺陷
    ],
  },
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
      "@next/next/no-img-element": "warn",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];

export default eslintConfig;
