import dotenv from "dotenv";

/** @type {import('next').NextConfig} */
const env = dotenv.config();

const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "placehold.co",
      },
    ],
  },
};

export default nextConfig;
