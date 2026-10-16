import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@hrm/shared"],
  poweredByHeader: false,
};

export default nextConfig;
