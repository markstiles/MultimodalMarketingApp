import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "X-Frame-Options",
            value: "ALLOW-FROM https://pages.sitecorecloud.io",
          },
          {
            key: "Content-Security-Policy",
            value:
              "frame-ancestors https://pages.sitecorecloud.io https://*.sitecorecloud.io",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
