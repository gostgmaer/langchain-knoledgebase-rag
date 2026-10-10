import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lets the production Dockerfile (frontend/Dockerfile) copy just
  // .next/standalone + .next/static + public into the runtime image,
  // instead of shipping the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
