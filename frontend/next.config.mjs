/** @type {import('next').NextConfig} */

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/docs",
        destination: "http://localhost:8000/api/docs/",
      },
      {
        source: "/api/schema",
        destination: "http://localhost:8000/api/schema/",
      },
      {
        source: "/api/openapi.json",
        destination: "http://localhost:8000/api/openapi.json",
      },
      {
        source: "/api/:path((?!docs$)(?!schema$).*)",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
