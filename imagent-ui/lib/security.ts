// Shared, in-process security primitives for the unauthenticated API routes:
// a fixed-window per-IP rate limiter, a concurrency cap for expensive work,
// a client-IP resolver, and an optional shared-secret auth gate. These are
// best-effort defenses that live in the Node process; behind a single-instance
// deployment (see deploy/Caddyfile) they meaningfully throttle abuse.

export type RateLimitResult = {
  allowed: boolean;
  retryAfterSeconds: number;
};

const RATE_LIMIT_WINDOW_MS = 60_000;
const MAX_TRACKED_BUCKETS = 10_000;

type RateLimitBucket = {
  count: number;
  resetAt: number;
};

const rateLimitBuckets = new Map<string, RateLimitBucket>();

/**
 * Fixed-window per-key rate limiter. Allows up to `limit` requests per
 * `windowMs` window. Namespacing the key (e.g. `generate:1.2.3.4`) keeps
 * separate routes from sharing a budget.
 */
export function rateLimit(key: string, limit: number, windowMs: number = RATE_LIMIT_WINDOW_MS): RateLimitResult {
  const now = Date.now();
  const bucket = rateLimitBuckets.get(key);

  if (!bucket || bucket.resetAt <= now) {
    if (rateLimitBuckets.size >= MAX_TRACKED_BUCKETS) {
      pruneExpiredBuckets(now);
    }
    rateLimitBuckets.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, retryAfterSeconds: 0 };
  }

  if (bucket.count >= limit) {
    return { allowed: false, retryAfterSeconds: Math.max(1, Math.ceil((bucket.resetAt - now) / 1000)) };
  }

  bucket.count += 1;
  return { allowed: true, retryAfterSeconds: 0 };
}

function pruneExpiredBuckets(now: number) {
  for (const [key, bucket] of rateLimitBuckets) {
    if (bucket.resetAt <= now) {
      rateLimitBuckets.delete(key);
    }
  }
}

/**
 * Best-effort client IP: first hop of `x-forwarded-for` (set by the reverse
 * proxy), falling back to a constant so the limiter still applies when the
 * header is absent.
 */
export function getClientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    const first = forwarded.split(",")[0]?.trim();
    if (first) {
      return first;
    }
  }
  return "unknown";
}

let activeGenerations = 0;

/** Try to reserve one of `max` concurrent slots. Returns false when saturated. */
export function tryAcquireGenerationSlot(max: number): boolean {
  if (activeGenerations >= max) {
    return false;
  }
  activeGenerations += 1;
  return true;
}

/** Release a slot reserved by tryAcquireGenerationSlot. Always call in a finally. */
export function releaseGenerationSlot(): void {
  activeGenerations = Math.max(0, activeGenerations - 1);
}

/**
 * Optional shared-secret gate. When `IMAGENT_UI_API_SECRET` is unset, the API
 * behaves exactly as before (no auth). When set, callers must present a
 * matching `x-imagent-secret` header.
 */
export function isRequestAuthorized(request: Request): boolean {
  const secret = String(process.env.IMAGENT_UI_API_SECRET || "").trim();
  if (!secret) {
    return true;
  }
  return request.headers.get("x-imagent-secret") === secret;
}
