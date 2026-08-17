/** @type {import('next').NextConfig} */
const nextConfig = {
  // Read backend URL from environment variable at build time.
  // Never hard-code localhost here.
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;
