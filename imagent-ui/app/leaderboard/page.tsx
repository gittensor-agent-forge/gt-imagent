import { ArrowUpRight, Swords, TrendingUp } from "lucide-react";
import type { Metadata } from "next";
import { LeaderboardBoard } from "@/app/components/LeaderboardBoard";
import { LandingBackgroundFx } from "@/app/components/LandingBackgroundFx";
import { type LeaderboardEntry, listLeaderboardEntries } from "@/lib/reports";

export const metadata: Metadata = {
  title: "Leaderboard | Imagent",
  description: "Imagent benchmark history, resolved pull request state, and the current benchmark king.",
  alternates: {
    canonical: "/leaderboard"
  },
  openGraph: {
    title: "Leaderboard | Imagent",
    description: "Imagent benchmark history, resolved pull request state, and the current benchmark king.",
    url: "/leaderboard"
  }
};

// Imported benchmark reports must be visible without a rebuild or redeploy.
export const dynamic = "force-dynamic";

export default async function LeaderboardPage() {
  const entries = await listLeaderboardEntries();
  const leader = entries[0] ?? null;
  const challenger = entries[1] ?? null;
  const track = buildFrontierTrack(entries);
  const firstTrackScore = track[0]?.score ?? null;
  const climb = firstTrackScore !== null && leader ? leader.score - firstTrackScore : null;

  return (
    <div className="imagent-landing leaderboard-live-page">
      <LandingBackgroundFx />

      {leader ? (
        <section className="leaderboard-frontier-region" aria-label="Frontier progress and closest rivalry">
          <FrontierTrack track={track} climb={climb} reportCount={entries.length} />
          <HeadToHead leader={leader} challenger={challenger} />
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
    return null;
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
    <section className="leaderboard-frontier-panel" aria-label="Frontier score over time">
      <div className="leaderboard-frontier-panel-head">
        <span className="leaderboard-frontier-panel-title"><TrendingUp size={15} /> Frontier Progress</span>
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
            <stop offset="0%" stopColor="rgba(0, 226, 251, 0.3)" />
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
            className={point.isNewFrontier ? "leaderboard-frontier-point leaderboard-frontier-point--new" : "leaderboard-frontier-point"}
          />
        ))}
      </svg>
      <div className="leaderboard-frontier-panel-foot">
        <span>{reportCount} report{reportCount === 1 ? "" : "s"} tracked</span>
        <span>{climb === null ? "baseline pending" : `${formatDelta(climb)} since first report`}</span>
      </div>
    </section>
  );
}

function HeadToHead({ challenger, leader }: { challenger: LeaderboardEntry | null; leader: LeaderboardEntry }) {
  const gap = challenger ? leader.score - challenger.score : null;

  return (
    <section className="leaderboard-rivalry-panel" aria-label="Current frontier versus closest challenger">
      <div className="leaderboard-rivalry-panel-head">
        <span className="leaderboard-frontier-panel-title"><Swords size={15} /> Head-to-Head</span>
      </div>
      <div className="leaderboard-rivalry-body">
        <RivalCard entry={leader} role="Frontier" tone="leader" />
        <div className="leaderboard-rivalry-divider" aria-hidden="true">
          <span />
        </div>
        {challenger ? (
          <RivalCard entry={challenger} role="Challenger" tone="challenger" gap={gap} />
        ) : (
          <div className="leaderboard-rivalry-empty">
            <span>No challenger yet</span>
            <p>A second report will start tracking how close the field is.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function RivalCard({ entry, gap, role, tone }: { entry: LeaderboardEntry; gap?: number | null; role: string; tone: "challenger" | "leader" }) {
  const topDimensions = [...entry.dimensions].sort((left, right) => right.score - left.score).slice(0, 2);

  return (
    <div className={`leaderboard-rivalry-card leaderboard-rivalry-card--${tone}`}>
      <span className="leaderboard-rivalry-role">{role}</span>
      <div className="leaderboard-rivalry-identity">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={entry.contributor.avatar_url || githubAvatarUrl(entry.contributor.login)} alt="" />
        <div>
          <strong>{entry.contributor.name || entry.contributor.login}</strong>
          <span>@{entry.contributor.login}</span>
        </div>
      </div>
      <div className="leaderboard-rivalry-score">
        <strong>{entry.score.toFixed(2)}</strong>
        {typeof gap === "number" ? <small>{gap <= 0.005 ? "tied" : `${gap.toFixed(2)} behind`}</small> : null}
      </div>
      {topDimensions.length > 0 ? (
        <div className="leaderboard-rivalry-dimensions">
          {topDimensions.map((dimension) => (
            <span key={dimension.name}>
              {formatDimension(dimension.name)} <strong>{dimension.score.toFixed(0)}</strong>
            </span>
          ))}
        </div>
      ) : null}
      <a className="leaderboard-rivalry-link" href={`/reports/${entry.runId}`}>
        View report <ArrowUpRight size={12} />
      </a>
    </div>
  );
}

function githubAvatarUrl(login: string) {
  return `https://github.com/${encodeURIComponent(login)}.png?size=96`;
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
