import { Activity, BarChart3, Crown, ImageIcon, Medal, ShieldCheck, Timer, TrendingUp, WalletCards } from "lucide-react";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { LeaderboardBoard } from "@/app/components/LeaderboardBoard";
import { IMAGENT_GENERATION_MODEL_NAME } from "@/lib/models";
import { type LeaderboardEntry, listLeaderboardEntries } from "@/lib/reports";

export const metadata: Metadata = {
  title: "Leaderboard | Imagent",
  description: "Imagent benchmark archive for Gittensor-powered image-agent research.",
  alternates: {
    canonical: "/leaderboard"
  },
  openGraph: {
    title: "Leaderboard | Imagent",
    description: "Imagent benchmark archive for Gittensor-powered image-agent research.",
    url: "/leaderboard"
  }
};

export const dynamic = "force-dynamic";

export default async function LeaderboardPage() {
  const entries = await listLeaderboardEntries();
  const topThree = entries.slice(0, 3);
  const merged = entries.filter((entry) => entry.pullRequest.state === "merged").length;
  const failed = entries.filter((entry) => entry.status === "fail").length;
  const averageScore = entries.length
    ? entries.reduce((total, entry) => total + entry.score, 0) / entries.length
    : 0;
  const topScore = entries[0]?.score ?? 0;
  const fastest = entries.length ? Math.min(...entries.map((entry) => entry.latencyP95Ms)) : 0;
  const totalCost = entries.reduce((total, entry) => total + entry.costUsd, 0);
  const leader = entries[0];
  const chronological = [...entries].sort((left, right) => Date.parse(left.completedAt) - Date.parse(right.completedAt));
  const latestReport = chronological[chronological.length - 1] ?? null;
  const projectBaseline = leader?.improvement.baselineScore ?? null;
  const projectDelta = leader?.improvement.delta ?? null;
  const eligible = entries.filter((entry) => entry.improvement.mergeEligible).length;
  const bestImprovement = entries.reduce<LeaderboardEntry | null>((best, entry) => {
    if (entry.improvement.delta === null) {
      return best;
    }
    if (!best || best.improvement.delta === null || entry.improvement.delta > best.improvement.delta) {
      return entry;
    }
    return best;
  }, null);
  const latestFive = chronological.slice(-5).reverse();
  const featureComparison = buildFeatureComparison(leader ?? null, entries);

  return (
    <div className="leaderboard-page">
      <section className="leaderboard-hero">
        <div className="leaderboard-hero-copy">
          <span className="page-kicker">Powered by Gittensor · subnet 74 · benchmark archive</span>
          <h1>Inspect Image-Agent Benchmark History</h1>
          <p>
            Every report is ranked by score, PR outcome, baseline delta, latency, cost, and judge dimensions.
            {" "}Generation is fixed to {IMAGENT_GENERATION_MODEL_NAME} through OpenRouter.
          </p>
        </div>
        <div className="leaderboard-visual" aria-hidden="true">
          <div className="visual-topline">
            <span>frontier miner</span>
            <strong>{leader ? `#${leader.rank}` : "#0"}</strong>
          </div>
          <div className="visual-avatar-row">
            {topThree.map((entry) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={entry.contributor.avatar_url || ""} alt="" key={entry.runId} />
            ))}
          </div>
          <div className="signal-rails">
            <span style={{ width: `${Math.max(8, Math.min(100, topScore))}%` }} />
            <span style={{ width: `${Math.max(8, Math.min(100, averageScore))}%` }} />
            <span style={{ width: `${entries.length ? 72 : 12}%` }} />
          </div>
          <div className="visual-ledger">
            <span>score {topScore.toFixed(2)}</span>
            <span>{entries.length} reports</span>
            <span>{eligible} eligible</span>
          </div>
        </div>
      </section>

      <section className="leaderboard-stats">
        <HeroStat icon={<Medal size={18} />} label="Top score" value={topScore.toFixed(2)} />
        <HeroStat icon={<TrendingUp size={18} />} label="Project delta" value={formatDelta(projectDelta)} />
        <HeroStat icon={<ShieldCheck size={18} />} label="Merge eligible" value={String(eligible)} />
        <HeroStat icon={<ImageIcon size={18} />} label="Avg score" value={averageScore.toFixed(1)} />
        <HeroStat icon={<Timer size={18} />} label="Fastest p95" value={`${fastest.toFixed(0)} ms`} />
        <HeroStat icon={<WalletCards size={18} />} label="Total cost" value={`$${totalCost.toFixed(4)}`} />
      </section>

      <section className="improvement-board" aria-label="Project improvement summary">
        <div className="improvement-board-copy">
          <span className="live-chip"><Activity size={13} /> Benchmark Archive</span>
          <h2>{formatDelta(projectDelta)} project improvement</h2>
          <p>
            Compared against {projectBaseline === null ? "the recorded baseline once benchmark ranking metadata is available" : `baseline ${projectBaseline.toFixed(2)}`}.
            {" "}Latest report {latestReport ? `finished ${formatDate(latestReport.completedAt)}` : "has not been imported yet"}.
          </p>
        </div>
        <div className="improvement-metrics">
          <ProjectMetric
            label="Current frontier"
            value={leader ? leader.score.toFixed(2) : "0.00"}
            detail={leader ? `@${leader.contributor.login} · ${leader.improvement.label}` : "waiting for reports"}
          />
          <ProjectMetric
            label="Best PR uplift"
            value={bestImprovement ? formatDelta(bestImprovement.improvement.delta) : "N/A"}
            detail={bestImprovement ? `@${bestImprovement.contributor.login} · ${pullRequestLabel(bestImprovement)}` : "baseline unavailable"}
          />
          <ProjectMetric
            label="Merged proof"
            value={String(merged)}
            detail={`${failed} failed or closed`}
          />
          <ProjectMetric
            label="Latest score"
            value={latestReport ? latestReport.score.toFixed(2) : "0.00"}
            detail={latestReport ? latestReport.improvement.label : "no run yet"}
          />
        </div>
        {latestFive.length > 0 ? (
          <div className="improvement-timeline custom-scrollbar" aria-label="Latest benchmark reports">
            {latestFive.map((entry) => (
              <a href={`/reports/${entry.runId}`} key={entry.runId}>
                <span className={`timeline-dot ${deltaTone(entry.improvement.delta)}`} />
                <strong>{entry.score.toFixed(1)}</strong>
                <small>{formatDelta(entry.improvement.delta)}</small>
              </a>
            ))}
          </div>
        ) : null}
      </section>

      <FeatureComparisonPanel
        baseline={featureComparison.baseline}
        current={leader ?? null}
        rows={featureComparison.rows}
      />

      <section className="podium-grid">
        {topThree.map((entry, index) => (
          <a className={`podium-card rank-${index + 1}`} href={`/reports/${entry.runId}`} key={entry.runId}>
            <div className="podium-rank">{index === 0 ? <Crown size={20} /> : `#${index + 1}`}</div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={entry.contributor.avatar_url || ""} alt="" />
            <div>
              <h2>{entry.contributor.name || entry.contributor.login}</h2>
              <p>@{entry.contributor.login}</p>
            </div>
            <strong>{entry.score.toFixed(2)}</strong>
            <span>{entry.pullRequest.state} · {pullRequestLabel(entry)}</span>
            <small>{formatDelta(entry.improvement.delta)} · {entry.improvement.label}</small>
          </a>
        ))}
      </section>

      <LeaderboardBoard entries={entries} />
    </div>
  );
}

type FeatureComparisonRow = {
  baseline: number | null;
  current: number | null;
  delta: number | null;
  name: string;
};

function HeroStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="hero-stat">
      {icon}
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function FeatureComparisonPanel({
  baseline,
  current,
  rows
}: {
  baseline: LeaderboardEntry | null;
  current: LeaderboardEntry | null;
  rows: FeatureComparisonRow[];
}) {
  const baselineScore = baseline?.score ?? current?.improvement.baselineScore ?? null;
  const overallDelta = current && baselineScore !== null ? current.score - baselineScore : null;
  const visibleRows: FeatureComparisonRow[] = [
    {
      baseline: baselineScore,
      current: current?.score ?? null,
      delta: overallDelta,
      name: "overall_benchmark"
    },
    ...rows
  ];
  const averageFeatureDelta = averageDelta(rows);

  return (
    <section className="feature-comparison" aria-label="Benchmark feature improvement">
      <div className="feature-comparison-header">
        <div>
          <span className="live-chip"><BarChart3 size={13} /> Feature delta</span>
          <h2>Before vs current frontier</h2>
          <p>
            {baseline
              ? `Comparing @${current?.contributor.login ?? "frontier"} against @${baseline.contributor.login}.`
              : current?.improvement.baselineScore !== null
                ? "The baseline score is known, but the matching baseline report has not been imported for feature-level comparison."
                : "Baseline feature scores will connect once benchmark reports include ranking metadata."}
          </p>
        </div>
        <div className="feature-summary-grid">
          <FeatureSummary label="Current top" value={current ? current.score.toFixed(2) : "0.00"} detail={current ? `@${current.contributor.login}` : "waiting"} />
          <FeatureSummary label="Before score" value={baselineScore === null ? "N/A" : baselineScore.toFixed(2)} detail={baseline ? `@${baseline.contributor.login}` : "baseline"} />
          <FeatureSummary label="Feature avg" value={formatDelta(averageFeatureDelta)} detail={rows.length ? `${rows.length} dimensions` : "pending"} />
        </div>
      </div>

      <div className="feature-legend" aria-hidden="true">
        <span><i className="before" />Before</span>
        <span><i className="current" />Current top</span>
      </div>

      <div className="feature-bars">
        {visibleRows.map((row) => (
          <div className="feature-row" key={row.name}>
            <div className="feature-row-label">
              <strong>{formatFeatureName(row.name)}</strong>
              <span>{formatScore(row.baseline)} before · {formatScore(row.current)} current</span>
            </div>
            <div className="feature-bar-stack">
              <div className="feature-bar-line before">
                <span style={{ width: scoreWidth(row.baseline) }} />
              </div>
              <div className="feature-bar-line current">
                <span style={{ width: scoreWidth(row.current) }} />
              </div>
            </div>
            <span className={`delta-badge ${deltaTone(row.delta)}`}>{formatDelta(row.delta)}</span>
          </div>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="feature-empty">
          Dimension-level bars will appear after OpenRouter vision judge reports include per-feature scores.
        </div>
      ) : null}
    </section>
  );
}

function FeatureSummary({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <div className="feature-summary">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function ProjectMetric({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <div className="project-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function pullRequestLabel(entry: LeaderboardEntry) {
  return entry.pullRequest.number === null ? "report metadata" : `PR #${entry.pullRequest.number}`;
}

function buildFeatureComparison(current: LeaderboardEntry | null, entries: LeaderboardEntry[]) {
  if (!current) {
    return { baseline: null, rows: [] as FeatureComparisonRow[] };
  }

  const baseline = findBaselineEntry(current, entries);
  const currentDimensions = dimensionMap(current);
  const baselineDimensions = baseline ? dimensionMap(baseline) : new Map<string, number>();
  const names = Array.from(new Set([...currentDimensions.keys(), ...baselineDimensions.keys()]));

  const rows = names
    .map((name) => {
      const currentScore = currentDimensions.get(name) ?? null;
      const baselineScore = baselineDimensions.get(name) ?? null;
      return {
        baseline: baselineScore,
        current: currentScore,
        delta: currentScore === null || baselineScore === null ? null : currentScore - baselineScore,
        name
      };
    })
    .sort((left, right) => {
      if (left.delta !== null && right.delta !== null && right.delta !== left.delta) {
        return right.delta - left.delta;
      }
      return formatFeatureName(left.name).localeCompare(formatFeatureName(right.name));
    });

  return { baseline, rows };
}

function findBaselineEntry(current: LeaderboardEntry, entries: LeaderboardEntry[]) {
  const candidates = entries.filter((entry) => entry.runId !== current.runId);
  const baselineCommit = current.improvement.baselineCommit;
  if (!baselineCommit) {
    return null;
  }

  const commitMatch = candidates.find((entry) => commitMatches(entry.commitSha, baselineCommit));
  if (commitMatch) {
    return commitMatch;
  }

  return null;
}

function dimensionMap(entry: LeaderboardEntry) {
  return new Map(entry.dimensions.map((dimension) => [dimension.name, dimension.score]));
}

function commitMatches(commitSha: string, baselineCommit: string) {
  return commitSha === baselineCommit || commitSha.startsWith(baselineCommit) || baselineCommit.startsWith(commitSha);
}

function averageDelta(rows: FeatureComparisonRow[]) {
  const deltas = rows
    .map((row) => row.delta)
    .filter((value): value is number => value !== null);
  if (!deltas.length) {
    return null;
  }
  return deltas.reduce((total, value) => total + value, 0) / deltas.length;
}

function scoreWidth(value: number | null) {
  if (value === null) {
    return "0%";
  }
  return `${Math.max(0, Math.min(100, value))}%`;
}

function formatScore(value: number | null) {
  return value === null ? "N/A" : value.toFixed(1);
}

function formatFeatureName(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
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

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "recently";
  }
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short"
  }).format(date);
}

function deltaTone(value: number | null) {
  if (value === null || Math.abs(value) < 0.005) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}
