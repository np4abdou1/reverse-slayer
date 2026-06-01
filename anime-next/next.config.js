/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'img.anslayer.com',
      },
    ],
  },
};

export default nextConfig;
