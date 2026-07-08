"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BookOpenText, Home, ImageIcon, RadioTower } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Route } from "next";

const navItems: Array<{ href: Route; label: string; icon: LucideIcon }> = [
  { href: "/", label: "Home", icon: Home },
  { href: "/generation", label: "Generation", icon: ImageIcon },
  { href: "/leaderboard", label: "Leaderboard", icon: BarChart3 },
  { href: "/whitepaper", label: "Whitepaper", icon: BookOpenText }
];

export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="app-header">
      <Link className="app-brand" href="/">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/imagent-ai-avatar.jpg" alt="" />
        <strong>IMAGENT</strong>
      </Link>
      <nav className="app-nav" aria-label="Primary navigation">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link className={active ? "active" : ""} href={item.href} key={item.href}>
              <Icon size={16} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="header-subnet" aria-label="Powered by Gittensor subnet 74">
        <RadioTower size={15} />
        <span>Powered by Gittensor</span>
        <small>SN74</small>
      </div>
    </header>
  );
}
