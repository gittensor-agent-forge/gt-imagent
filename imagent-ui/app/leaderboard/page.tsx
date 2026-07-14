import {
  Activity,
  BarChart3,
  Crown,
  Gauge,
  ImageIcon,
  Layers3,
  Medal,
  Radar,
  Scale,
  ShieldCheck,
  Timer,
  TrendingUp,
  WalletCards
} from "lucide-react";
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

type ScoreBucket = {
  count: number;
  label: string;
  max: number;
  min: number;
};

type CapabilitySummary = {
  average: number;
  name: string;
  samples: number;
};

export default async function LeaderboardPage() {
  const entries = await listLeaderboardEntries();
  const topThree = entries.slice(0, 3);
  const merged = entries.filter((entry) => entry.pullRequest.state === "merged").length;
  const failed = entries.filter((entry) => entry.status === "fail").length;
  const passCount = entries.filter((entry) => entry.status === "pass").length;
  const averageScore = entries.length
    ? entries.reduce((total, entry) => total + entry.score, 0) / entries.length
    : 0;
  const topScore = entries[0]?.score ?? 0;
  const fastest = entries.length ? Math.min(...entries.map((entry) => entry.latencyP95Ms)) : 0;
  const totalCost = entries.reduce((total, entry) => total + entry.costUsd, 0);
  const leader = entries[0] ?? null;
  const runnerUp = entries[1] ?? null;
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
  const scoreFloor = entries.at(-1)?.score ?? topScore;
  const scoreSpread = entries.length > 1 ? topScore - scoreFloor : 0;
  const scoreDistribution = buildScoreDistribution(entries);
  const capabilitySummary = buildCapabilitySummary(entries);

  return (
    <div className="leaderboard-page">
      <section className="leaderboard-hero">
        <div className="leaderboard-hero-copy">
          <span className="page-kicker">Powered by Gittensor - subnet 74 - benchmark archive</span>
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
            detail={leader ? `@${leader.contributor.login} - ${leader.improvement.label}` : "waiting for reports"}
          />
          <ProjectMetric
            label="Best PR uplift"
            value={bestImprovement ? formatDelta(bestImprovement.improvement.delta) : "N/A"}
            detail={bestImprovement ? `@${bestImprovement.contributor.login} - ${pullRequestLabel(bestImprovement)}` : "baseline unavailable"}
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

      <ReviewConsolePanel
        averageScore={averageScore}
        capabilitySummary={capabilitySummary}
        eligible={eligible}
        entries={entries}
        leader={leader}
        passCount={passCount}
        runnerUp={runnerUp}
        scoreDistribution={scoreDistribution}
        scoreSpread={scoreSpread}
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
            <span>{entry.pullRequest.state} - {pullRequestLabel(entry)}</span>
            <small>{formatDelta(entry.improvement.delta)} - {entry.improvement.label}</small>
          </a>
        ))}
      </section>

      <LeaderboardBoard entries={entries} />
    </div>
  );
}

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

function ReviewConsolePanel({
  averageScore,
  capabilitySummary,
  eligible,
  entries,
  leader,
  passCount,
  runnerUp,
  scoreDistribution,
  scoreSpread
}: {
  averageScore: number;
  capabilitySummary: CapabilitySummary[];
  eligible: number;
  entries: LeaderboardEntry[];
  leader: LeaderboardEntry | null;
  passCount: number;
  runnerUp: LeaderboardEntry | null;
  scoreDistribution: ScoreBucket[];
  scoreSpread: number;
}) {
  const weakest = [...capabilitySummary].reverse().slice(0, 3);
  const strongest = capabilitySummary.slice(0, 3);
  const runnerGap = leader && runnerUp ? leader.score - runnerUp.score : null;
  const passRate = entries.length ? (passCount / entries.length) * 100 : 0;

  return (
    <section className="leaderboard-review-console" aria-label="Benchmark review console">
      <div className="review-console-header">
        <div>
          <span className="live-chip"><Radar size={13} /> Review console</span>
          <h2>Compare the archive without opening every report</h2>
          <p>
            Real report data is folded into score bands, capability averages, frontier gap,
            and review signals so maintainers can scan quality, consistency, and merge readiness.
          </p>
        </div>
        <div className="review-console-metrics" aria-label="Archive health">
          <ReviewMetric icon={<BarChart3 size={15} />} label="Average" value={averageScore.toFixed(1)} />
          <ReviewMetric icon={<Scale size={15} />} label="Spread" value={scoreSpread.toFixed(1)} />
          <ReviewMetric icon={<ShieldCheck size={15} />} label="Pass rate" value={`${passRate.toFixed(0)}%`} />
        </div>
      </div>

      <div className="review-console-grid">
        <article className="review-card review-card-wide">
          <div className="review-card-head">
            <span><Gauge size={14} /> Score distribution</span>
            <strong>{entries.length} reports</strong>
          </div>
          <div className="score-bands">
            {scoreDistribution.map((bucket) => (
              <div className="score-band" key={bucket.label}>
                <div>
                  <strong>{bucket.label}</strong>
                  <span>{bucket.count} runs</span>
                </div>
                <i>
                  <b style={{ width: entries.length ? `${Math.max(6, (bucket.count / entries.length) * 100)}%` : "0%" }} />
                </i>
              </div>
            ))}
          </div>
        </article>

        <article className="review-card">
          <div className="review-card-head">
            <span><Crown size={14} /> Frontier gap</span>
            <strong>{formatDelta(runnerGap)}</strong>
          </div>
          <div className="frontier-duel">
            <ReviewCompetitor entry={leader} label="Leader" />
            <ReviewCompetitor entry={runnerUp} label="Runner-up" />
          </div>
        </article>

        <article className="review-card">
          <div className="review-card-head">
            <span><Layers3 size={14} /> Capability profile</span>
            <strong>{capabilitySummary.length || 0}</strong>
          </div>
          {capabilitySummary.length > 0 ? (
            <div className="capability-review">
              <div>
                <span>Strongest</span>
                {strongest.map((item) => <CapabilityPill item={item} key={`strong-${item.name}`} />)}
              </div>
              <div>
                <span>Needs attention</span>
                {weakest.map((item) => <CapabilityPill item={item} key={`weak-${item.name}`} />)}
              </div>
            </div>
          ) : (
            <p className="review-card-empty">Dimension scores will appear once judge reports include capability data.</p>
          )}
        </article>

        <article className="review-card review-card-signals">
          <div className="review-card-head">
            <span><Activity size={14} /> Review signals</span>
            <strong>{eligible}</strong>
          </div>
          <div className="signal-list">
            <span><ShieldCheck size={14} /> {eligible} merge eligible</span>
            <span><Medal size={14} /> {passCount} passing reports</span>
            <span><Timer size={14} /> {formatLatency(entries)}</span>
            <span><WalletCards size={14} /> {formatCost(entries)}</span>
          </div>
        </article>
      </div>
    </section>
  );
}

function ReviewMetric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="review-metric">
      {icon}
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function ReviewCompetitor({ entry, label }: { entry: LeaderboardEntry | null; label: string }) {
  return (
    <div className="review-competitor">
      <span>{label}</span>
      {entry ? (
        <>
          <div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={entry.contributor.avatar_url || ""} alt="" />
            <strong>@{entry.contributor.login}</strong>
          </div>
          <small>{entry.score.toFixed(2)} - {pullRequestLabel(entry)}</small>
        </>
      ) : (
        <small>No report yet</small>
      )}
    </div>
  );
}

function CapabilityPill({ item }: { item: CapabilitySummary }) {
  return (
    <div className="capability-pill">
      <div>
        <strong>{formatFeatureName(item.name)}</strong>
        <small>{item.samples} samples</small>
      </div>
      <span>{item.average.toFixed(1)}</span>
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

function buildScoreDistribution(entries: LeaderboardEntry[]): ScoreBucket[] {
  const buckets: ScoreBucket[] = [
    { count: 0, label: "90-100", max: 100, min: 90 },
    { count: 0, label: "75-89", max: 89.999, min: 75 },
    { count: 0, label: "60-74", max: 74.999, min: 60 },
    { count: 0, label: "<60", max: 59.999, min: -Infinity }
  ];

  entries.forEach((entry) => {
    const bucket = buckets.find((item) => entry.score >= item.min && entry.score <= item.max);
    if (bucket) {
      bucket.count += 1;
    }
  });

  return buckets;
}

function buildCapabilitySummary(entries: LeaderboardEntry[]) {
  const totals = new Map<string, { samples: number; total: number }>();
  entries.forEach((entry) => {
    entry.dimensions.forEach((dimension) => {
      const existing = totals.get(dimension.name) ?? { samples: 0, total: 0 };
      existing.samples += 1;
      existing.total += dimension.score;
      totals.set(dimension.name, existing);
    });
  });

  return Array.from(totals.entries())
    .map(([name, value]) => ({
      average: value.samples ? value.total / value.samples : 0,
      name,
      samples: value.samples
    }))
    .sort((left, right) => right.average - left.average);
}

function formatLatency(entries: LeaderboardEntry[]) {
  if (!entries.length) {
    return "No latency";
  }
  const fastest = Math.min(...entries.map((entry) => entry.latencyP95Ms));
  const slowest = Math.max(...entries.map((entry) => entry.latencyP95Ms));
  return `${fastest.toFixed(0)}-${slowest.toFixed(0)} ms p95`;
}

function formatCost(entries: LeaderboardEntry[]) {
  if (!entries.length) {
    return "$0.00000 total";
  }
  const total = entries.reduce((sum, entry) => sum + entry.costUsd, 0);
  return `$${total.toFixed(5)} total`;
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
