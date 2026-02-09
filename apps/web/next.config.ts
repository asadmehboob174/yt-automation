import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  experimental: {
    // turbopack options removed as they are causing build errors
  },
};

export default nextConfig;
