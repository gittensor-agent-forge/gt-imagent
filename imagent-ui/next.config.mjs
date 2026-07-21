/** @type {import('next').NextConfig} */

// Defense-in-depth security headers applied to every route. The CSP is scoped
// to what this app actually loads:
//  - scripts/styles: self + inline (Next.js hydration bootstrap and next/font
//    inject inline <script>/<style>; next/font self-hosts the font files).
//  - images: self (generated artifacts, brand assets), data: (inline fallback
//    avatars), and GitHub avatar hosts used by leaderboard contributors.
//  - connect: self (the browser only talks to our own API routes; OpenRouter
//    is reached server-side).
const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://github.com https://*.githubusercontent.com",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'"
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }
];

const nextConfig = {
  typedRoutes: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders
      }
    ];
  }
};

export default nextConfig;
