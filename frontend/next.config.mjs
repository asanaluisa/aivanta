/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Linting is not part of the build; type errors still fail it.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
