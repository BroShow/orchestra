import type { NextConfig } from "next";

const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const config: NextConfig = {
  transpilePackages: ["@orchestra/shared-types"],
  // Forward /api/* to the FastAPI backend in dev so the browser and the
  // API share an origin (no CORS pain).
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiBase}/:path*` },
    ];
  },
};

export default config;
