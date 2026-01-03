import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  images: {
    domains: ['oaidalleapiprodscus.blob.core.windows.net'],
  },
};

export default nextConfig;
