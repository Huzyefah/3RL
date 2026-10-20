import type { NextConfig } from "next";

// cacheComponents is intentionally NOT enabled: with it, Next 16 removes the
// `dynamic`/`runtime` route segment config that the D2 SSE proxy relies on.
const nextConfig: NextConfig = {
  output: "standalone",
  compress: false, // gzip would buffer SSE frames (D2)
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
