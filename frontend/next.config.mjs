/** @type {import('next').NextConfig} */

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/docs",
        destination: "http://backend:8000/api/docs/",
      },
      {
        source: "/api/schema",
        destination: "http://backend:8000/api/schema/",
      },
      {
        source: "/api/:path((?!docs$)(?!schema$).*)",
        destination: "http://backend:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
