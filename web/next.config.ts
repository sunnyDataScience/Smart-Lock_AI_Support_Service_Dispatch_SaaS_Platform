import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloud Run 部署用 standalone 輸出：把 prod 必要檔案打包成
  // .next/standalone/，runtime image 只複製此包 + .next/static + public，
  // 不帶完整 node_modules，image size 從 1GB+ 降到 200MB 級
  output: "standalone",

  experimental: {
    // 自動把 named import 轉成 deep import（per-file），讓 webpack 樹搖只
    // 留實際用到的 icons / chart 子模組，避免 lucide-react 全套 1500+ icons
    // 與 recharts 全套圖表元件被一起打進 bundle
    optimizePackageImports: ["lucide-react", "recharts"],
  },
};

export default nextConfig;
