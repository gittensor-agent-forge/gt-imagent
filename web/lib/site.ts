export const DEFAULT_PUBLIC_SITE_URL = "https://tryimagent.com";

export function resolvePublicSiteUrl() {
  const candidate = String(process.env.IMAGENT_PUBLIC_SITE_URL || DEFAULT_PUBLIC_SITE_URL).trim();
  try {
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    url.hash = "";
    url.search = "";
    if (url.pathname === "/") {
      url.pathname = "";
    } else {
      url.pathname = url.pathname.replace(/\/+$/, "");
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return DEFAULT_PUBLIC_SITE_URL;
  }
}
