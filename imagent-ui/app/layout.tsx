import type { Metadata } from "next";
import { JetBrains_Mono, Space_Grotesk } from "next/font/google";
import type { ReactNode } from "react";
import { AppFooter } from "@/app/components/AppFooter";
import { AppHeader } from "@/app/components/AppHeader";
import { ScrollActivity } from "@/app/components/ScrollActivity";
import { SiteBackground } from "@/app/components/SiteBackground";
import { resolvePublicSiteUrl } from "@/lib/site";
import "./styles.css";

const jetBrainsMono = JetBrains_Mono({
  display: "swap",
  subsets: ["latin"],
  variable: "--font-jetbrains"
});

const spaceGrotesk = Space_Grotesk({
  display: "swap",
  subsets: ["latin"],
  variable: "--font-space-grotesk"
});

const publicSiteUrl = resolvePublicSiteUrl();

export const metadata: Metadata = {
  title: "Imagent",
  description: "Open platform for image-generation agents, benchmarks, and Gittensor-powered contributor rounds.",
  metadataBase: new URL(publicSiteUrl),
  alternates: {
    canonical: "/"
  },
  openGraph: {
    title: "Imagent",
    description: "Open platform for image-generation agents, benchmarks, and Gittensor-powered contributor rounds.",
    url: publicSiteUrl,
    siteName: "Imagent"
  },
  icons: {
    icon: "/brand/imagent-ai-avatar.jpg",
    apple: "/brand/imagent-ai-avatar.jpg"
  }
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${jetBrainsMono.variable} ${spaceGrotesk.variable}`}>
        <SiteBackground />
        <ScrollActivity />
        <AppHeader />
        <main>{children}</main>
        <AppFooter />
      </body>
    </html>
  );
}
