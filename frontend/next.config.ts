import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  watchOptions: {
    pollIntervalMs: 1000,
  },
};

export default nextConfig;
