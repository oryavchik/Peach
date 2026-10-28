import type { NextConfig } from "next";

// "standalone" builds the small server bundle the Docker image runs.
// "export" builds a static site for S3 + CloudFront; set by scripts/deploy-frontend.sh.
const output =
  (process.env.NEXT_OUTPUT as "standalone" | "export") ?? "standalone";

const nextConfig: NextConfig = {
  output,
  // The export target has no server to optimize images on the fly.
  ...(output === "export" ? { images: { unoptimized: true } } : {}),
  ...(process.env.NODE_ENV === "development" && process.env.LOCAL_API_PROXY_URL
    ? {
        async rewrites() {
          const api = process.env.LOCAL_API_PROXY_URL!.replace(/\/+$/, "");
          return [
            {
              source: "/api/v1/:path*",
              destination: `${api}/api/v1/:path*`,
            },
            {
              source: "/agenda-parser",
              destination: "http://127.0.0.1:8001/",
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
