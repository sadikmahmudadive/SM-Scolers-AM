import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@hrm/shared"],
  poweredByHeader: false,
  // Backup restore and CSV import post their file contents through server actions (default limit 1 MB).
  experimental: { serverActions: { bodySizeLimit: "6mb" } },
};

export default nextConfig;
