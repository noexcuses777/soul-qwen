import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  poweredByHeader: false,
  experimental: { proxyTimeout: 1_800_000 },
  async rewrites() {
    // One same-origin API; no model client, weights or inference in Next.js.
    const origin = process.env.SOUL_API_ORIGIN || "http://127.0.0.1:8001";
    const url = new URL(origin);
    if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) {
      throw new Error("SOUL_API_ORIGIN must point to the local Qwen backend");
    }
    return [{ source: "/api/:path*", destination: `${url.origin}/api/:path*` }];
  },
};

export default nextConfig;
