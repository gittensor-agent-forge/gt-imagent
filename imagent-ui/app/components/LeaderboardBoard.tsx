"use client";

import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  GitMerge,
  GitPullRequestClosed,
  Minus,
  Search,
  Timer,
  TrendingDown,
  TrendingUp,
  WalletCards,
  XCircle
} from "lucide-react";
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

    return () => {
      window.clearInterval(timer);
    };
  }, [router]);

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
        entry.benchmarkVersion,
        entry.improvement.label,
        entry.generationModel,
        entry.judgeModel,
        entry.runId
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [entries, filter, query]);

  const visibleStats = useMemo(() => {
    const score = visibleEntries.length
      ? visibleEntries.reduce((total, entry) => total + entry.score, 0) / visibleEntries.length
      : 0;
    const eligible = visibleEntries.filter((entry) => entry.improvement.mergeEligible).length;
    const pass = visibleEntries.filter((entry) => entry.status === "pass").length;
    const cost = visibleEntries.reduce((total, entry) => total + entry.costUsd, 0);
    return {
      cost,
      eligible,
      pass,
      score
    };
  }, [visibleEntries]);

  return (
    <section className="subnet-table">
      <div className="table-toolbar">
        <div>
          <h2>Benchmark Archive</h2>
          <p>{visibleEntries.length} of {entries.length} reports - refreshes every 30s</p>
          <div className="table-summary-grid" aria-label="Filtered benchmark summary">
            <SummaryChip label="Average" value={visibleStats.score.toFixed(1)} />
            <SummaryChip label="Eligible" value={String(visibleStats.eligible)} />
            <SummaryChip label="Pass" value={String(visibleStats.pass)} />
            <SummaryChip label="Cost" value={`$${visibleStats.cost.toFixed(4)}`} />
          </div>
        </div>
        <div className="leaderboard-controls">
          <span className="leaderboard-live"><Activity size={13} /> Archive</span>
          <label className="leaderboard-search">
            <Search size={15} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search miner, repo, PR"
            />
          </label>
          <div className="filter-chips" aria-label="Leaderboard filters">
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

      <div className="leaderboard-table-wrap">
        <table className="leaderboard-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Miner</th>
              <th>Pull Request</th>
              <th>Score</th>
              <th>Improvement</th>
              <th>Generation Model</th>
              <th>Result</th>
              <th>Latency</th>
              <th>Cost</th>
              <th>Report</th>
            </tr>
          </thead>
          <tbody>
            {visibleEntries.map((entry) => (
              <tr key={entry.runId}>
                <td><span className="rank-pill">#{entry.rank}</span></td>
                <td>
                  <div className="miner-cell">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={entry.contributor.avatar_url || ""} alt="" />
                    <div>
                      <strong>{entry.contributor.name || entry.contributor.login}</strong>
                      <span>@{entry.contributor.login}</span>
                    </div>
                  </div>
                </td>
                <td>
                  <div className="pr-cell">
                    <strong>{entry.pullRequest.number === null ? "No PR metadata" : `#${entry.pullRequest.number}`}</strong>
                    <small>{entry.pullRequest.title}</small>
                    <span className={`pr-state ${entry.pullRequest.state}`}>
                      {entry.pullRequest.state === "merged" ? (
                        <GitMerge size={13} />
                      ) : entry.pullRequest.state === "unknown" ? (
                        <Minus size={13} />
                      ) : (
                        <GitPullRequestClosed size={13} />
                      )}
                      {entry.pullRequest.state}
                    </span>
                    {entry.pullRequest.source === "derived" ? <small>metadata derived locally</small> : null}
                  </div>
                </td>
                <td>
                  <div className="score-cell">
                    <strong>{entry.score.toFixed(2)}</strong>
                    <span><i style={{ width: `${Math.max(3, Math.min(100, entry.score))}%` }} /></span>
                    <small className="score-context">{formatScoreContext(entry)}</small>
                    {entry.dimensions.length > 0 ? (
                      <div className="dimension-strip">
                        {entry.dimensions.slice(0, 3).map((dimension) => (
                          <small key={dimension.name}>{formatDimension(dimension.name)} {dimension.score.toFixed(0)}</small>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </td>
                <td>
                  <div className="improvement-cell">
                    <span className={`delta-badge ${deltaTone(entry.improvement.delta)}`}>
                      {deltaIcon(entry.improvement.delta)}
                      {formatDelta(entry.improvement.delta)}
                    </span>
                    <small>{entry.improvement.label}</small>
                    {entry.improvement.baselineScore !== null ? (
                      <em>vs {entry.improvement.baselineScore.toFixed(2)}</em>
                    ) : (
                      <em>baseline pending</em>
                    )}
                  </div>
                </td>
                <td>
                  <div className="model-cell">
                    <strong>{formatModelName(entry.generationModel)}</strong>
                    <small>{entry.generationModel || "model unavailable"}</small>
                  </div>
                </td>
                <td>
                  <span className={`result-badge ${entry.status}`}>
                    {entry.status === "pass" ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                    {entry.status}
                  </span>
                  <small className="benchmark-version">{entry.benchmarkVersion}</small>
                </td>
                <td><span className="metric-inline"><Timer size={13} /> {entry.latencyP95Ms.toFixed(0)} ms</span></td>
                <td><span className="metric-inline"><WalletCards size={13} /> ${entry.costUsd.toFixed(5)}</span></td>
                <td>
                  <a className="report-link" href={`/reports/${entry.runId}`}>
                    View <ArrowUpRight size={14} />
                  </a>
                </td>
              </tr>
            ))}
            {visibleEntries.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={10}>No benchmark reports match this view.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="table-summary-chip">
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function formatScoreContext(entry: LeaderboardEntry) {
  const capabilityCount = entry.dimensions.length;
  const baseline = entry.improvement.baselineScore;
  if (baseline !== null) {
    return `${capabilityCount} dimensions vs ${baseline.toFixed(1)}`;
  }
  return capabilityCount ? `${capabilityCount} dimensions` : "dimension data pending";
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

function deltaIcon(value: number | null) {
  if (value === null || Math.abs(value) < 0.005) {
    return <Minus size={13} />;
  }
  return value > 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />;
}

function formatDimension(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatModelName(value: string | null) {
  if (!value) {
    return "Unknown";
  }
  if (value === "google/gemini-3.1-flash-image") {
    return "Gemini 3.1 Flash Image";
  }
  return value.split("/").pop()?.replace(/[-_]+/g, " ") || value;
}
