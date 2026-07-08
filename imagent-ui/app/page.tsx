import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  CircleMinus,
  Crown,
  GitCompareArrows,
  GitPullRequestArrow,
  ImageIcon,
  ShieldCheck,
  Sparkles,
  Trophy,
  Workflow
} from "lucide-react";
import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AgentStepper } from "@/app/components/AgentStepper";
import { EffectCard, LandingBackgroundFx } from "@/app/components/EffectCard";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import { IMAGENT_GENERATION_MODEL_NAME } from "@/lib/models";
import type { LeaderboardEntry } from "@/lib/reports";
import { listLeaderboardEntries } from "@/lib/reports";

export const metadata: Metadata = {
  title: "Imagent | Image Generation Agents",
  description: "A Gittensor-powered open competition for image-generation agents built around one fixed image model.",
  alternates: {
    canonical: "/"
  },
  openGraph: {
    title: "Imagent | Image Generation Agents",
    description: "A Gittensor-powered open competition for image-generation agents built around one fixed image model.",
    url: "/"
  }
};

export const dynamic = "force-dynamic";

type ContrastCardContent = {
  copy: string;
  eyebrow: string;
  icon: LucideIcon;
  items: string[];
  title: string;
  tone: "active" | "flat";
};

const contrastCards: { agent: ContrastCardContent; direct: ContrastCardContent } = {
  direct: {
    copy: "One prompt with no audit trail",
    eyebrow: "Baseline",
    icon: ImageIcon,
    items: [
      "Prompt becomes the whole plan",
      "Missing context stays hidden",
      "No critique before output",
      "Result is hard to audit"
    ],
    title: "Direct Model Call",
    tone: "flat"
  },
  agent: {
    copy: "Planner critique and benchmark evidence",
    eyebrow: "Imagent",
    icon: Workflow,
    items: [
      "Intent is parsed before generation",
      "Context becomes a structured prompt",
      "Output is critiqued and scored",
      "Winning strategy becomes reference"
    ],
    title: "Agent Trajectory",
    tone: "active"
  }
};

const contributorSteps: Array<{
  copy: string;
  detail: string;
  icon: LucideIcon;
  label: string;
  title: string;
  tone: "submit" | "bench" | "promote";
}> = [
  {
    copy: "One focused agent PR enters the round",
    detail: "Contributor PRs stay eligible when they only update the agent",
    icon: GitPullRequestArrow,
    label: "Pull Request",
    title: "Submit Agent",
    tone: "submit"
  },
  {
    copy: "Same model benchmark score",
    detail: "The run must improve beyond the threshold over the last winner",
    icon: Workflow,
    label: "Round Gate",
    title: "Benchmark Proof",
    tone: "bench"
  },
  {
    copy: "Best eligible strategy becomes the new reference",
    detail: "The bot updates last_winner and archives the code in winners",
    icon: Trophy,
    label: "Promotion",
    title: "Archive Winner",
    tone: "promote"
  }
];

export default async function HomePage() {
  const entries = await listLeaderboardEntries();
  const leader = entries[0] ?? null;
  const eligible = entries.filter((entry) => entry.improvement.mergeEligible).length;
  const merged = entries.filter((entry) => entry.pullRequest.state === "merged").length;

  return (
    <div className="imagent-landing">
      <LandingBackgroundFx />
      <ScrollReveal />
      <section className="imagent-landing__hero" aria-labelledby="home-title">
        <div className="imagent-landing__hero-copy" data-reveal="fade-right">
          <div className="imagent-landing__eyebrow">
            <span className="imagent-landing__pulse" />
            Open image-agent bench
          </div>
          <h1 id="home-title">One Model Better Agents</h1>
          <p className="imagent-landing__hero-lede">
            Imagent keeps the image model fixed and lets agent code compete through public benchmark rounds
          </p>
          <div className="imagent-landing__actions">
            <Link className="imagent-landing__button imagent-landing__button--primary" href="/generation">
              Generate <ArrowRight size={17} />
            </Link>
            <Link className="imagent-landing__button imagent-landing__button--secondary" href="/leaderboard">
              Leaderboard <BarChart3 size={17} />
            </Link>
          </div>
          <div className="imagent-landing__hero-strip" aria-label="Competition constraints" data-reveal="fade-up" data-reveal-delay="2">
            <EffectCard animated className="imagent-landing__hero-card" radius={17}>
              <ImageIcon size={17} />
              <span>Model</span>
              <strong>{IMAGENT_GENERATION_MODEL_NAME}</strong>
            </EffectCard>
            <EffectCard animated className="imagent-landing__hero-card" radius={17}>
              <ShieldCheck size={17} />
              <span>Rule</span>
              <strong>Beat Last Winner</strong>
            </EffectCard>
          </div>
          <div className="imagent-landing__hero-signal" aria-label="Live round signal" data-reveal="fade-up" data-reveal-delay="3">
            <span>
              <strong>2x daily</strong>
              <small>Round cadence</small>
            </span>
            <span>
              <strong>{entries.length}</strong>
              <small>Reports scored</small>
            </span>
            <span>
              <strong>{eligible}</strong>
              <small>Eligible agents</small>
            </span>
          </div>
        </div>

        <div className="imagent-landing__reveal-shell" data-reveal="scale" data-reveal-delay="2">
          <RoundCockpit entries={entries} eligible={eligible} leader={leader} merged={merged} />
        </div>
      </section>

      <section className="imagent-landing__section imagent-landing__section--contrast">
        <SectionIntro
          eyebrow="Compare"
          icon={GitCompareArrows}
          title={<>Direct Prompt <span className="imagent-landing__title-vs">vs</span> Agent Run</>}
          copy="Same model stronger orchestration"
        />
        <div className="imagent-landing__versus-arena" aria-label="One-shot versus agentic comparison">
          <div className="imagent-landing__reveal-shell" data-reveal="fade-right" data-reveal-delay="1">
            <ContrastCard card={contrastCards.direct} />
          </div>
          <div className="imagent-landing__versus-line" aria-hidden="true" data-reveal="scale" data-reveal-delay="2">
            <span />
            <strong>VS</strong>
            <span />
          </div>
          <div className="imagent-landing__reveal-shell" data-reveal="fade-left" data-reveal-delay="3">
            <ContrastCard card={contrastCards.agent} />
          </div>
        </div>
      </section>

      <section className="imagent-landing__section imagent-landing__section--rail">
        <SectionIntro
          eyebrow="Loop"
          icon={Workflow}
          title="Clean Agent Trajectory"
          copy="From request to winning agent"
        />
        <AgentStepper />
      </section>

      <section className="imagent-landing__section imagent-landing__section--submission">
        <div className="imagent-landing__submission-head">
          <SectionIntro
            eyebrow="Contribute"
            icon={GitPullRequestArrow}
            title="Simple Path To Promotion"
            copy="One PR per round Benchmark gate Winner history"
          />
          <div className="imagent-landing__promotion-rule" aria-label="Promotion rule" data-reveal="fade-left" data-reveal-delay="1">
            <span><Crown size={15} /> Promotion rule</span>
            <strong>Highest Eligible Score Wins</strong>
            <p>Threshold must beat the last winner</p>
          </div>
        </div>
        <div className="imagent-landing__promotion-flow" aria-label="Contribution promotion flow">
          {contributorSteps.map((step, index) => {
            const Icon = step.icon;
            return (
              <div
                className={`imagent-landing__promotion-node imagent-landing__promotion-node--${step.tone}`}
                data-reveal="fade-up"
                data-reveal-delay={index + 1}
                key={step.title}
              >
                <EffectCard
                  animated={step.tone === "bench"}
                  className={`imagent-landing__promotion-card imagent-landing__promotion-card--${step.tone}`}
                  radius={24}
                >
                  <div className="imagent-landing__promotion-card-head">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <Icon size={22} />
                  </div>
                  <strong>{step.label}</strong>
                  <h3>{step.title}</h3>
                  <p>{step.copy}</p>
                  <small>{step.detail}</small>
                </EffectCard>
              </div>
            );
          })}
        </div>
        <div className="imagent-landing__promotion-notes" aria-label="Promotion safeguards" data-reveal="fade-up" data-reveal-delay="4">
          <span><ShieldCheck size={14} /> agent only PR</span>
          <span><Workflow size={14} /> benchmark scored</span>
          <span><Trophy size={14} /> public winner code</span>
        </div>
      </section>

      <section className="imagent-landing__cta" aria-labelledby="landing-cta-title">
        <div className="imagent-landing__cta-copy" data-reveal="scale">
          <span className="imagent-landing__section-kicker">
            <Sparkles size={13} />
            Start
          </span>
          <h2 id="landing-cta-title">Enter The Agent Bench</h2>
          <p>Generate with the fixed model inspect the score and improve the agent</p>
          <div className="imagent-landing__actions">
            <Link className="imagent-landing__button imagent-landing__button--primary" href="/generation">
              Open Generation <Sparkles size={17} />
            </Link>
            <Link className="imagent-landing__button imagent-landing__button--secondary" href="/leaderboard">
              View Leaderboard <BarChart3 size={17} />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function RoundCockpit({
  eligible,
  entries,
  leader,
  merged
}: {
  eligible: number;
  entries: LeaderboardEntry[];
  leader: LeaderboardEntry | null;
  merged: number;
}) {
  return (
    <EffectCard animated className="imagent-landing__cockpit" radius={22}>
      <div className="imagent-landing__cockpit-top">
        <span><Trophy size={16} /> Winner</span>
        <strong className="imagent-landing__king-mark" aria-label={leader ? `Rank ${leader.rank} winner` : "Open round winner"}>
          <Crown size={30} />
        </strong>
      </div>
      <EffectCard className="imagent-landing__winner" glareOpacity={0.12} radius={16}>
        <span className="imagent-landing__winner-avatar" aria-hidden="true">
          {leader?.contributor.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={leader.contributor.avatar_url} alt="" />
          ) : (
            <Trophy size={24} />
          )}
        </span>
        <div>
          <span>Agent</span>
          <strong>{leader?.agentName ?? "No reports"}</strong>
          <p>{leader ? `@${leader.contributor.login}` : "Open round"}</p>
        </div>
      </EffectCard>
      <div className="imagent-landing__cockpit-metrics">
        <EffectCard className="imagent-landing__metric-tile" glareOpacity={0.12} radius={16}>
          <span>Score</span>
          <strong>{leader ? leader.score.toFixed(2) : "0.00"}</strong>
        </EffectCard>
        <EffectCard className="imagent-landing__metric-tile" glareOpacity={0.12} radius={16}>
          <span>Delta</span>
          <strong>{formatDelta(leader?.improvement.delta ?? null)}</strong>
        </EffectCard>
      </div>
      <div className="imagent-landing__cockpit-footer">
        <span>{entries.length} reports</span>
        <span>{eligible} eligible</span>
        <span>{merged} merged</span>
      </div>
    </EffectCard>
  );
}

function SectionIntro({
  copy,
  eyebrow,
  icon: Icon,
  title
}: {
  copy: string;
  eyebrow: string;
  icon?: LucideIcon;
  title: ReactNode;
}) {
  return (
    <div className="imagent-landing__section-intro" data-reveal="fade-up">
      <span className="imagent-landing__section-kicker">
        {Icon ? <Icon size={13} /> : null}
        {eyebrow}
      </span>
      <h2>{title}</h2>
      <p>{copy}</p>
    </div>
  );
}

function ContrastCard({ card }: { card: ContrastCardContent }) {
  const Icon = card.icon;
  const ItemIcon = card.tone === "active" ? CheckCircle2 : CircleMinus;

  return (
    <EffectCard className={`imagent-landing__contrast-card imagent-landing__contrast-card--${card.tone}`} radius={18}>
      <div className="imagent-landing__contrast-card-head">
        <span>{card.eyebrow}</span>
        <Icon size={22} />
      </div>
      <h3>{card.title}</h3>
      <p>{card.copy}</p>
      <ul>
        {card.items.map((item) => (
          <li key={item}><ItemIcon size={16} /> {item}</li>
        ))}
      </ul>
    </EffectCard>
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
