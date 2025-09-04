/** @type {import('next').NextConfig} */

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api",
        destination: "http://localhost:8000",
      },
      {
        source: "/api/docs",
        destination: "http://localhost:8000/api/docs",
      },
      {
        source: "/openapi.json",
        destination: "http://localhost:8000/openapi.json",
      },
      {
				source: "/api/:path*",
				destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
