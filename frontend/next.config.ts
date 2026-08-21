import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Stop leaking `X-Powered-By: Next.js` to every response.
  poweredByHeader: false,

  // Security headers applied to every route. CSP is deliberately NOT included
  // here — the app loads Google Identity Services (accounts.google.com/gsi)
  // for sign-in, and a correct CSP for that needs its own testing pass.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
