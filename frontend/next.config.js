/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false, // Disable to prevent WebSocket double connections
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://192.168.1.3:11111/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
