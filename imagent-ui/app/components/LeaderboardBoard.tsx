"use client";

import { Activity, ArrowUpRight, CheckCircle2, GitMerge, GitPullRequestClosed, Minus, Search, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { LeaderboardEntry } from "@/lib/reports";

type Filter = "all" | "eligible" | "merged" | "closed" | "failed";

const filters: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" },
  { id: "eligible", label: "Eligible" },
  { id: "merged", label: "Merged" },
  { id: "closed", label: "Closed" },
  { id: "failed", label: "Failed" }
];

export function LeaderboardBoard({ entries }: { entries: LeaderboardEntry[] }) {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const timer = window.setInterval(() => {
      router.refresh();
    }, 30000);
    return () => window.clearInterval(timer);
  }, [router]);

  const maxScore = useMemo(
    () => entries.reduce((max, entry) => Math.max(max, entry.score), 0) || 100,
    [entries]
  );

  const visibleEntries = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return entries.filter((entry) => {
      const matchesFilter =
        filter === "all" ||
        (filter === "eligible" && entry.improvement.mergeEligible) ||
        (filter === "merged" && entry.pullRequest.state === "merged") ||
        (filter === "closed" && entry.pullRequest.state === "closed") ||
        (filter === "failed" && entry.status === "fail");

      if (!matchesFilter) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }

      const haystack = [
        entry.contributor.login,
        entry.contributor.name,
        entry.repository,
        entry.agentName,
        entry.pullRequest.title,
        entry.pullRequest.number === null ? "" : String(entry.pullRequest.number),
        entry.improvement.label,
        entry.runId
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [entries, filter, query]);

  return (
    <section className="lb-board" aria-label="All benchmarked miners">
      <div className="lb-board-head">
        <div>
          <h2>All benchmarked miners</h2>
          <p>
            {visibleEntries.length} of {entries.length} reports · refreshes every 30s
          </p>
        </div>
        <div className="lb-board-controls">
          <span className="lb-live">
            <Activity size={13} /> Archive
          </span>
          <label className="lb-search">
            <Search size={15} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search miner, repo, PR"
              aria-label="Search miners"
            />
          </label>
          <div className="lb-filters" aria-label="Leaderboard filters">
            {filters.map((item) => (
              <button
                className={filter === item.id ? "active" : ""}
                type="button"
                key={item.id}
                onClick={() => setFilter(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="lb-rows">
        <div className="lb-row lb-row-header" aria-hidden="true">
          <span>#</span>
          <span>Miner</span>
          <span>Pull request</span>
          <span>Score</span>
          <span>Δ</span>
          <span>Result</span>
          <span />
        </div>
        {visibleEntries.map((entry) => (
          <a className="lb-row" href={`/reports/${entry.runId}`} key={entry.runId}>
            <span className="lb-row-rank">#{entry.rank}</span>
            <span className="lb-row-miner">
              <span className="lb-row-avatar" aria-hidden="true">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={entry.contributor.avatar_url || ""} alt="" />
              </span>
              <span className="lb-row-miner-id">
                <strong>{entry.contributor.name || entry.contributor.login}</strong>
                <small>@{entry.contributor.login}</small>
              </span>
            </span>
            <span className="lb-row-pr">
              <strong>{entry.pullRequest.number === null ? "report" : `PR #${entry.pullRequest.number}`}</strong>
              <span className={`lb-pill lb-pr-state ${entry.pullRequest.state}`}>
                {entry.pullRequest.state === "merged" ? (
                  <GitMerge size={12} />
                ) : entry.pullRequest.state === "unknown" ? (
                  <Minus size={12} />
                ) : (
                  <GitPullRequestClosed size={12} />
                )}
                {entry.pullRequest.state}
              </span>
            </span>
            <span className="lb-row-score">
              <span className="lb-row-bar">
                <i style={{ width: `${Math.max(4, (entry.score / maxScore) * 100)}%` }} />
              </span>
              <strong>{entry.score.toFixed(2)}</strong>
            </span>
            <span className={`lb-delta ${deltaTone(entry.improvement.delta)}`}>{formatDelta(entry.improvement.delta)}</span>
            <span className={`lb-result ${entry.status === "fail" ? "fail" : "pass"}`}>
              {entry.status === "fail" ? <XCircle size={13} /> : <CheckCircle2 size={13} />}
              {entry.status === "fail" ? "fail" : "pass"}
            </span>
            <span className="lb-row-open">
              <ArrowUpRight size={16} />
            </span>
          </a>
        ))}
        {visibleEntries.length === 0 ? <div className="lb-empty">No miners match this view yet.</div> : null}
      </div>
    </section>
  );
}

function formatDelta(value: number | null) {
  if (value === null) {
    return "N/A";
  }
  if (Math.abs(value) < 0.005) {
    return "+0.00";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function deltaTone(value: number | null) {
  if (value === null || Math.abs(value) < 0.005) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}
