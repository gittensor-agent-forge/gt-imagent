"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Route } from "next";

const footerLinks: Array<{ href: Route; label: string }> = [
  { href: "/", label: "Home" },
  { href: "/generation", label: "Generation" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/whitepaper", label: "Whitepaper" }
];

export function AppFooter() {
  const pathname = usePathname();

  if (pathname === "/generation" || pathname.startsWith("/generation/")) {
    return null;
  }

  return (
    <footer className="imagent-footer">
      <div className="imagent-footer__inner">
        <div className="imagent-footer__row imagent-footer__row--top">
          <Link className="imagent-footer__brand" href="/">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/imagent-ai-avatar.jpg" alt="" />
            <span>
              <strong>IMAGENT</strong>
              <small>Powered by Gittensor SN74</small>
            </span>
          </Link>

          <nav className="imagent-footer__nav" aria-label="Footer navigation">
            {footerLinks.map((item) => (
              <Link href={item.href} key={item.href}>{item.label}</Link>
            ))}
          </nav>
        </div>

        <div className="imagent-footer__row imagent-footer__row--bottom">
          <p>© 2026 Imagent AI. Open image-agent research.</p>
          <div className="imagent-footer__socials" aria-label="Social links">
            <a className="imagent-footer__social-link imagent-footer__social-link--discord" href="https://discord.com/invite/bittensor" rel="noreferrer" target="_blank" aria-label="Discord">
              <DiscordIcon />
            </a>
            <a className="imagent-footer__social-link imagent-footer__social-link--github" href="https://github.com/imagent-ai/imagent-ui" rel="noreferrer" target="_blank" aria-label="GitHub">
              <GitHubIcon />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

function DiscordIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="24" viewBox="0 0 24 24" width="24">
      <path
        d="M19.66 5.08A17.88 17.88 0 0 0 15.33 3.7c-.18.34-.4.8-.54 1.16a16.66 16.66 0 0 0-5.58 0A9.2 9.2 0 0 0 8.67 3.7a17.9 17.9 0 0 0-4.34 1.38C1.59 9.23.85 13.27 1.22 17.25a17.85 17.85 0 0 0 5.33 2.72c.43-.59.81-1.21 1.14-1.88-.63-.24-1.23-.53-1.8-.87.15-.11.3-.23.44-.35a12.8 12.8 0 0 0 11.34 0l.44.35c-.57.34-1.17.63-1.8.87.33.67.71 1.29 1.14 1.88a17.88 17.88 0 0 0 5.33-2.72c.45-4.61-.76-8.62-3.12-12.17ZM8.85 14.8c-1.04 0-1.9-.97-1.9-2.16s.84-2.16 1.9-2.16c1.06 0 1.92.98 1.9 2.16 0 1.19-.84 2.16-1.9 2.16Zm6.3 0c-1.04 0-1.9-.97-1.9-2.16s.84-2.16 1.9-2.16c1.06 0 1.9.98 1.9 2.16s-.84 2.16-1.9 2.16Z"
        fill="currentColor"
      />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="24" viewBox="0 0 24 24" width="24">
      <path
        d="M12 2C6.48 2 2 6.6 2 12.26c0 4.53 2.87 8.37 6.84 9.72.5.1.68-.22.68-.49 0-.24-.01-.88-.01-1.73-2.78.62-3.37-1.38-3.37-1.38-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.63.07-.63 1 .08 1.53 1.06 1.53 1.06.9 1.57 2.36 1.11 2.94.85.09-.66.35-1.11.63-1.37-2.22-.26-4.55-1.14-4.55-5.08 0-1.12.39-2.04 1.03-2.76-.1-.26-.45-1.3.1-2.72 0 0 .84-.28 2.75 1.05a9.24 9.24 0 0 1 5 0c1.9-1.33 2.74-1.05 2.74-1.05.55 1.42.2 2.46.1 2.72.64.72 1.03 1.64 1.03 2.76 0 3.95-2.34 4.82-4.57 5.07.36.32.68.94.68 1.9 0 1.37-.01 2.48-.01 2.82 0 .27.18.59.69.49A10.19 10.19 0 0 0 22 12.26C22 6.6 17.52 2 12 2Z"
        fill="currentColor"
      />
    </svg>
  );
}
