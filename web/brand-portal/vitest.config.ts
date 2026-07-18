import path from "node:path";
import { defineConfig } from "vitest/config";

// vitest 無法讀 tsconfig paths，補 "@" alias 讓單元測試可載入 src/ 模組
// （UAT round2 修復新增 tests/unit/format.test.ts 需要）
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
