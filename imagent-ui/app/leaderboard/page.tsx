import { Crown, Layers, Medal, ShieldCheck, TrendingUp, Trophy } from "lucide-react";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { EffectCard } from "@/app/components/EffectCard";
import { LandingBackgroundFx } from "@/app/components/LandingBackgroundFx";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import { LeaderboardBoard } from "@/app/components/LeaderboardBoard";
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
  const leader = entries[0] ?? null;
  const runnersUp = entries.slice(1, 3);
  const topScore = leader?.score ?? 0;
  const projectDelta = leader?.improvement.delta ?? null;
  const eligible = entries.filter((entry) => entry.improvement.mergeEligible).length;
  const topDimensions = leader
    ? [...leader.dimensions].sort((left, right) => right.score - left.score).slice(0, 4)
    : [];

  return (
    <div className="imagent-landing lb-page">
      <LandingBackgroundFx />
      <ScrollReveal />

      <section className="lb-hero" aria-labelledby="leaderboard-title">
        <div className="lb-hero-copy" data-reveal="fade-right">
          <span className="imagent-landing__section-kicker">
            <Trophy size={13} />
            Gittensor · Subnet 74 · Benchmark archive
          </span>
          <h1 id="leaderboard-title">
            The frontier of <span>image agents</span>.
          </h1>
          <p className="lb-hero-lede">
            Every merged agent is scored on the same fixed model — {IMAGENT_GENERATION_MODEL_NAME} — and ranked by
            benchmark improvement over the last winner.
          </p>
          <div className="lb-stat-rail" aria-label="Leaderboard summary">
            <LbStat icon={<Medal size={16} />} label="Top score" value={topScore.toFixed(2)} />
            <LbStat icon={<TrendingUp size={16} />} label="Project delta" value={formatDelta(projectDelta)} tone={deltaTone(projectDelta)} />
            <LbStat icon={<ShieldCheck size={16} />} label="Eligible" value={String(eligible)} />
            <LbStat icon={<Layers size={16} />} label="Reports" value={String(entries.length)} />
          </div>
        </div>

        <div className="lb-spotlight-shell" data-reveal="scale" data-reveal-delay="2">
          <EffectCard animated className="lb-spotlight" radius={24}>
            <div className="lb-spotlight-top">
              <span className="lb-spotlight-badge">
                <Crown size={14} /> Frontier miner
              </span>
              <span className="lb-spotlight-rank">{leader ? `#${leader.rank}` : "#0"}</span>
            </div>
            <div className="lb-spotlight-id">
              <span className="lb-spotlight-avatar" aria-hidden="true">
                {leader?.contributor.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={leader.contributor.avatar_url} alt="" />
                ) : (
                  <Trophy size={26} />
                )}
              </span>
              <div>
                <strong>{leader?.contributor.name || leader?.contributor.login || "No reports yet"}</strong>
                <p>{leader ? `@${leader.contributor.login}` : "Waiting for the first scored round"}</p>
              </div>
            </div>
            <div className="lb-spotlight-score">
              <strong>{leader ? leader.score.toFixed(2) : "0.00"}</strong>
              <span className={`lb-delta ${deltaTone(projectDelta)}`}>{formatDelta(projectDelta)}</span>
            </div>
            <div className="lb-spotlight-meta">
              <span className={`lb-result ${leader?.status === "fail" ? "fail" : "pass"}`}>
                {leader?.status === "fail" ? "fail" : "pass"}
              </span>
              <span className="lb-pill">{leader ? pullRequestLabel(leader) : "no PR"}</span>
              <span className={`lb-pill lb-pr-state ${leader?.pullRequest.state ?? "unknown"}`}>
                {leader?.pullRequest.state ?? "—"}
              </span>
            </div>
            {topDimensions.length ? (
              <div className="lb-dims">
                {topDimensions.map((dimension) => (
                  <div className="lb-dim" key={dimension.name}>
                    <span>{formatFeatureName(dimension.name)}</span>
                    <div className="lb-dim-bar">
                      <i style={{ width: `${clampPct(dimension.score)}%` }} />
                    </div>
                    <small>{dimension.score.toFixed(0)}</small>
                  </div>
                ))}
              </div>
            ) : null}
          </EffectCard>
        </div>
      </section>

      {runnersUp.length ? (
        <section className="lb-podium" aria-label="Runners up">
          {runnersUp.map((entry) => (
            <EffectCard className="lb-podium-card" glareOpacity={0.12} radius={20} key={entry.runId}>
              <span className="lb-podium-rank">
                <Medal size={15} />#{entry.rank}
              </span>
              <span className="lb-podium-avatar" aria-hidden="true">
                {entry.contributor.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={entry.contributor.avatar_url} alt="" />
                ) : null}
              </span>
              <div className="lb-podium-id">
                <strong>{entry.contributor.name || entry.contributor.login}</strong>
                <p>@{entry.contributor.login}</p>
              </div>
              <div className="lb-podium-score">
                <strong>{entry.score.toFixed(2)}</strong>
                <span className={`lb-delta ${deltaTone(entry.improvement.delta)}`}>{formatDelta(entry.improvement.delta)}</span>
              </div>
            </EffectCard>
          ))}
        </section>
      ) : null}

      <LeaderboardBoard entries={entries} />
    </div>
  );
}

function LbStat({ icon, label, tone, value }: { icon: ReactNode; label: string; tone?: string; value: string }) {
  return (
    <div className="lb-stat">
      <span className="lb-stat-icon">{icon}</span>
      <div>
        <strong className={tone ? `lb-stat-value ${tone}` : "lb-stat-value"}>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function pullRequestLabel(entry: LeaderboardEntry) {
  return entry.pullRequest.number === null ? "report metadata" : `PR #${entry.pullRequest.number}`;
}

function formatFeatureName(value: string) {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function clampPct(value: number) {
  return Math.max(4, Math.min(100, value));
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
