import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloud Run 部署用 standalone 輸出：把 prod 必要檔案打包成
  // .next/standalone/，runtime image 只複製此包 + .next/static + public，
  // 不帶完整 node_modules，image size 從 1GB+ 降到 200MB 級
  output: "standalone",
};

export default nextConfig;
