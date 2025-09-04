import dotenv from "dotenv";

/** @type {import('next').NextConfig} */
const env = dotenv.config();

const nextConfig = {
  reactStrictMode: true,
  trailingSlash: true,
  async rewrites() {
    return {
      beforeFiles: [
        // Handle API routes before checking for pages/public files
        {
          source: "/api/:path*/",
          destination: "http://localhost:8000/api/:path*/",
        },
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
      ],
    };
  },
};

export default nextConfig;
