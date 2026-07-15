import { ArrowUpRight, Crown, ImageIcon, Medal, ShieldCheck, Sparkles, Swords, Timer, TrendingUp, WalletCards } from "lucide-react";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { LandingBackgroundFx } from "@/app/components/LandingBackgroundFx";
import { LeaderboardBoard } from "@/app/components/LeaderboardBoard";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import { StaticEffectCard } from "@/app/components/StaticEffectCard";
import { IMAGENT_GENERATION_MODEL_NAME } from "@/lib/models";
import { type LeaderboardEntry, listLeaderboardEntries } from "@/lib/reports";

export const metadata: Metadata = {
  title: "Leaderboard | Imagent",
  description: "Live Imagent benchmark leaderboard for Gittensor-powered image-agent PR rounds.",
  alternates: {
    canonical: "/leaderboard"
  },
  openGraph: {
    title: "Leaderboard | Imagent",
    description: "Live Imagent benchmark leaderboard for Gittensor-powered image-agent PR rounds.",
    url: "/leaderboard"
  }
};

export const dynamic = "force-dynamic";

export default async function LeaderboardPage() {
  const entries = await listLeaderboardEntries();
  const topThree = entries.slice(0, 3);
  const averageScore = entries.length
    ? entries.reduce((total, entry) => total + entry.score, 0) / entries.length
    : 0;
  const topScore = entries[0]?.score ?? 0;
  const fastest = entries.length ? Math.min(...entries.map((entry) => entry.latencyP95Ms)) : 0;
  const totalCost = entries.reduce((total, entry) => total + entry.costUsd, 0);
  const leader = entries[0] ?? null;
  const challenger = entries[1] ?? null;
  const eligible = entries.filter((entry) => entry.improvement.mergeEligible).length;
  const track = buildFrontierTrack(entries);
  const firstTrackScore = track[0]?.score ?? null;
  const climb = firstTrackScore !== null ? topScore - firstTrackScore : null;

  return (
    <div className="imagent-landing leaderboard-page">
      <LandingBackgroundFx />
      <ScrollReveal />

      <section className="leaderboard-frontier-hero" aria-labelledby="leaderboard-title" data-reveal="fade-up">
        <div className="leaderboard-frontier-copy">
          <span className="page-kicker leaderboard-kicker">
            <Sparkles size={13} /> Powered by Gittensor &middot; subnet 74 &middot; official eval
          </span>
          <h1 id="leaderboard-title">The frontier keeps climbing.</h1>
          <p>
            Every completed report raises or holds the bar. Generation is fixed to {IMAGENT_GENERATION_MODEL_NAME}
            {" "}through OpenRouter, so every point of climb reflects a better agent, not a better model.
          </p>
        </div>

        <FrontierTrack track={track} climb={climb} reportCount={entries.length} />
      </section>

      <section className="leaderboard-rail" aria-label="Benchmark summary">
        <RailStat icon={<Medal size={16} />} label="Top score" value={topScore.toFixed(2)} />
        <RailStat icon={<TrendingUp size={16} />} label="Total climb" value={climb === null ? "N/A" : formatDelta(climb)} />
        <RailStat icon={<ShieldCheck size={16} />} label="Merge eligible" value={String(eligible)} />
        <RailStat icon={<ImageIcon size={16} />} label="Avg score" value={averageScore.toFixed(1)} />
        <RailStat icon={<Timer size={16} />} label="Fastest p95" value={`${fastest.toFixed(0)} ms`} />
        <RailStat icon={<WalletCards size={16} />} label="Total cost" value={`$${totalCost.toFixed(4)}`} />
      </section>

      {leader ? (
        <HeadToHead leader={leader} challenger={challenger} />
      ) : null}

      {topThree.length > 0 ? (
        <section className="leaderboard-podium" aria-label="Top three miners">
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
              <span>{entry.pullRequest.state} &middot; {pullRequestLabel(entry)}</span>
              <small>{formatDelta(entry.improvement.delta)} &middot; {entry.improvement.label}</small>
            </a>
          ))}
        </section>
      ) : null}

      <LeaderboardBoard entries={entries} />
    </div>
  );
}

type FrontierPoint = {
  completedAt: string;
  contributor: string;
  isNewFrontier: boolean;
  score: number;
};

function buildFrontierTrack(entries: LeaderboardEntry[]): FrontierPoint[] {
  const chronological = [...entries].sort((left, right) => Date.parse(left.completedAt) - Date.parse(right.completedAt));
  let runningMax = -Infinity;
  return chronological.map((entry) => {
    const isNewFrontier = entry.score >= runningMax;
    runningMax = Math.max(runningMax, entry.score);
    return {
      completedAt: entry.completedAt,
      contributor: entry.contributor.login,
      isNewFrontier,
      score: runningMax
    };
  });
}

function FrontierTrack({ climb, reportCount, track }: { climb: number | null; reportCount: number; track: FrontierPoint[] }) {
  if (track.length === 0) {
    return (
      <StaticEffectCard className="leaderboard-frontier-track leaderboard-frontier-track--empty" radius={22}>
        <span>No benchmark reports yet. The frontier line starts with the first completed round.</span>
      </StaticEffectCard>
    );
  }

  const scores = track.map((point) => point.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const span = Math.max(max - min, 1);
  const width = 100;
  const height = 42;
  const stepX = track.length > 1 ? width / (track.length - 1) : 0;
  const coords = track.map((point, index) => {
    const x = track.length > 1 ? index * stepX : width / 2;
    const y = height - ((point.score - min) / span) * (height - 8) - 4;
    return { ...point, x, y };
  });
  const linePath = coords.map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${coords[coords.length - 1].x.toFixed(2)},${height} L${coords[0].x.toFixed(2)},${height} Z`;
  const latest = track[track.length - 1];

  return (
    <StaticEffectCard className="leaderboard-frontier-track" radius={22}>
      <div className="leaderboard-frontier-track-head">
        <span>Frontier score over time</span>
        <strong>{latest.score.toFixed(2)}</strong>
      </div>
      <svg
        className="leaderboard-frontier-svg"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Frontier score climbed from ${scores[0].toFixed(2)} to ${latest.score.toFixed(2)} across ${track.length} completed reports.`}
      >
        <defs>
          <linearGradient id="frontier-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#85f5ad" />
            <stop offset="55%" stopColor="#00e2fb" />
            <stop offset="100%" stopColor="#0171f9" />
          </linearGradient>
          <linearGradient id="frontier-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(0, 226, 251, 0.32)" />
            <stop offset="100%" stopColor="rgba(0, 226, 251, 0)" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#frontier-area)" stroke="none" />
        <path d={linePath} fill="none" stroke="url(#frontier-line)" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
        {coords.map((point) => (
          <circle
            key={point.completedAt + point.contributor}
            cx={point.x}
            cy={point.y}
            r={point.isNewFrontier ? 1.9 : 1.1}
            className={point.isNewFrontier ? "frontier-point frontier-point--new" : "frontier-point"}
          />
        ))}
      </svg>
      <div className="leaderboard-frontier-track-foot">
        <span>{reportCount} report{reportCount === 1 ? "" : "s"} tracked</span>
        <span>{climb === null ? "baseline pending" : `${formatDelta(climb)} since first report`}</span>
      </div>
    </StaticEffectCard>
  );
}

function HeadToHead({ challenger, leader }: { challenger: LeaderboardEntry | null; leader: LeaderboardEntry }) {
  const gap = challenger ? leader.score - challenger.score : null;

  return (
    <section className="leaderboard-versus" aria-label="Current frontier versus closest challenger">
      <VersusCard entry={leader} role="Current frontier" tone="leader" />

      <div className="leaderboard-versus-divider" aria-hidden="true">
        <span />
        <strong><Swords size={18} /></strong>
        <span />
      </div>

      {challenger ? (
        <VersusCard entry={challenger} role="Closest challenger" tone="challenger" gap={gap} />
      ) : (
        <div className="leaderboard-versus-empty">
          <span>No challenger yet</span>
          <p>Once a second report lands, this side tracks how close the field is to the frontier.</p>
        </div>
      )}
    </section>
  );
}

function VersusCard({ entry, gap, role, tone }: { entry: LeaderboardEntry; gap?: number | null; role: string; tone: "challenger" | "leader" }) {
  const topDimensions = [...entry.dimensions].sort((left, right) => right.score - left.score).slice(0, 3);

  return (
    <StaticEffectCard className={`leaderboard-versus-card leaderboard-versus-card--${tone}`} radius={22}>
      <span className="leaderboard-versus-role">{role}</span>
      <div className="leaderboard-versus-identity">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={entry.contributor.avatar_url || ""} alt="" />
        <div>
          <strong>{entry.contributor.name || entry.contributor.login}</strong>
          <span>@{entry.contributor.login}</span>
        </div>
      </div>
      <div className="leaderboard-versus-score">
        <strong>{entry.score.toFixed(2)}</strong>
        {typeof gap === "number" ? <small>{gap <= 0.005 ? "tied with the frontier" : `${gap.toFixed(2)} behind`}</small> : null}
      </div>
      {topDimensions.length > 0 ? (
        <div className="leaderboard-versus-dimensions">
          {topDimensions.map((dimension) => (
            <span key={dimension.name}>
              {formatDimension(dimension.name)} <strong>{dimension.score.toFixed(0)}</strong>
            </span>
          ))}
        </div>
      ) : null}
      <a className="leaderboard-versus-link" href={`/reports/${entry.runId}`}>
        View report <ArrowUpRight size={13} />
      </a>
    </StaticEffectCard>
  );
}

function RailStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="leaderboard-rail-stat">
      {icon}
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function pullRequestLabel(entry: LeaderboardEntry) {
  return entry.pullRequest.number === null ? "report metadata" : `PR #${entry.pullRequest.number}`;
}

function formatDimension(value: string) {
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
