import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker/Node.js 生产模式
  output: 'standalone',
  devIndicators: false,
  reactCompiler: true,
  // 静态导出需要禁用图片优化（或使用外部服务）
  images: {
    unoptimized: true,
  },
};

export default nextConfig;

