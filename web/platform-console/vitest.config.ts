import path from "node:path";
import { defineConfig } from "vitest/config";

// vitest 無法讀 tsconfig paths，補 "@" alias 讓單元測試可載入 src/ 模組
// （範式同 brand-portal，WBS 1.4.1 三站複製輪引入）
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
