/** @type {import('next').NextConfig} */

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/docs",
        destination: "http://localhost:8000/docs/",
      },
      {
        source: "/api/openapi.json",
        destination: "http://localhost:8000/api/openapi.json",
      },
      {
        source: "/api/:path((?!openapi$)(?!docs$).*)",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
