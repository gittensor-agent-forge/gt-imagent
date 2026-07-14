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
import { LandingBackgroundFx } from "@/app/components/LandingBackgroundFx";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import { StaticEffectCard } from "@/app/components/StaticEffectCard";
import { IMAGENT_GENERATION_MODEL_NAME } from "@/lib/models";
import type { LeaderboardEntry } from "@/lib/reports";
import { listLeaderboardEntries } from "@/lib/reports";

export const metadata: Metadata = {
  title: "Imagent | Image Generation Agents",
  description: "A Gittensor-powered research platform for image-generation agents and transparent benchmark history.",
  alternates: {
    canonical: "/"
  },
  openGraph: {
    title: "Imagent | Image Generation Agents",
    description: "A Gittensor-powered research platform for image-generation agents and transparent benchmark history.",
    url: "/"
  }
};

// Benchmark imports are infrequent, so ISR keeps the landing route responsive
// while reflecting new reports shortly after they are written.
export const revalidate = 60;

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
    copy: "One focused Leaderboard UI PR enters manual review",
    detail: "Only approved Leaderboard UI files can change",
    icon: GitPullRequestArrow,
    label: "Pull Request",
    title: "Submit Design",
    tone: "submit"
  },
  {
    copy: "A screenshot or video proves the visual change",
    detail: "Missing evidence keeps the PR open with needs-evidence",
    icon: Workflow,
    label: "Evidence Gate",
    title: "Show The Result",
    tone: "bench"
  },
  {
    copy: "Maintainer review decides whether the design lands",
    detail: "Leaderboard UI work is never benchmarked or auto-merged",
    icon: Trophy,
    label: "Manual Review",
    title: "Merge Deliberately",
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
            Imagent keeps the image model fixed and makes image-agent progress visible through public benchmark history
          </p>
          <div className="imagent-landing__actions">
            <Link className="imagent-landing__button imagent-landing__button--primary" href="/generation">
              Generate <ArrowRight size={17} />
            </Link>
            <Link className="imagent-landing__button imagent-landing__button--secondary" href="/leaderboard">
              Leaderboard <BarChart3 size={17} />
            </Link>
          </div>
          <div className="imagent-landing__hero-strip" aria-label="Competition constraints">
            <StaticEffectCard className="imagent-landing__hero-card" radius={17}>
              <ImageIcon size={17} />
              <span>Model</span>
              <strong>{IMAGENT_GENERATION_MODEL_NAME}</strong>
            </StaticEffectCard>
            <StaticEffectCard className="imagent-landing__hero-card" radius={17}>
              <ShieldCheck size={17} />
              <span>Current Track</span>
              <strong>Leaderboard UI</strong>
            </StaticEffectCard>
          </div>
          <div className="imagent-landing__hero-signal" aria-label="Project signals">
            <span>
              <strong>Manual</strong>
              <small>UI review</small>
            </span>
            <span>
              <strong>{entries.length}</strong>
              <small>Reports archived</small>
            </span>
            <span>
              <strong>{merged}</strong>
              <small>Merged PRs</small>
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
            title="Simple Path To Review"
            copy="One PR Visual evidence Manual merge"
          />
          <div className="imagent-landing__promotion-rule" aria-label="Promotion rule">
            <span><Crown size={15} /> Review rule</span>
            <strong>Scoped Leaderboard UI</strong>
            <p>Visual evidence is required before manual review</p>
          </div>
        </div>
        <div className="imagent-landing__promotion-flow" aria-label="Contribution promotion flow" data-reveal="fade-up" data-reveal-delay="1">
          {contributorSteps.map((step, index) => {
            const Icon = step.icon;
            return (
              <div
                className={`imagent-landing__promotion-node imagent-landing__promotion-node--${step.tone}`}
                key={step.title}
              >
                <StaticEffectCard className={`imagent-landing__promotion-card imagent-landing__promotion-card--${step.tone}`} radius={24}>
                  <div className="imagent-landing__promotion-card-head">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <Icon size={22} />
                  </div>
                  <strong>{step.label}</strong>
                  <h3>{step.title}</h3>
                  <p>{step.copy}</p>
                  <small>{step.detail}</small>
                </StaticEffectCard>
              </div>
            );
          })}
        </div>
        <div className="imagent-landing__promotion-notes" aria-label="Promotion safeguards">
          <span><ShieldCheck size={14} /> Leaderboard scope</span>
          <span><Workflow size={14} /> visual evidence</span>
          <span><Trophy size={14} /> manual merge</span>
        </div>
      </section>

      <section className="imagent-landing__cta" aria-labelledby="landing-cta-title">
        <div className="imagent-landing__cta-copy" data-reveal="scale">
          <span className="imagent-landing__section-kicker">
            <Sparkles size={13} />
            Start
          </span>
          <h2 id="landing-cta-title">Explore The Agent Bench</h2>
          <p>Generate with the fixed model inspect the archive and follow active Leaderboard work</p>
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
  const archiveLeaderLabel = leader
    ? "Rank " + leader.rank + " archive leader"
    : "No archive leader";

  return (
    <section className="imagent-landing__cockpit" aria-label="Benchmark archive leader">
      <div className="imagent-landing__cockpit-top">
        <span><Trophy size={16} /> Archive Leader</span>
        <strong className="imagent-landing__king-mark" aria-label={archiveLeaderLabel}>
          <Crown size={30} />
        </strong>
      </div>
      <div className="imagent-landing__winner">
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
          <p>{leader ? "@" + leader.contributor.login : "Awaiting report"}</p>
        </div>
      </div>
      <div className="imagent-landing__cockpit-metrics">
        <div className="imagent-landing__metric-tile">
          <span>Score</span>
          <strong>{leader ? leader.score.toFixed(2) : "0.00"}</strong>
        </div>
        <div className="imagent-landing__metric-tile">
          <span>Delta</span>
          <strong>{formatDelta(leader?.improvement.delta ?? null)}</strong>
        </div>
      </div>
      <div className="imagent-landing__cockpit-footer">
        <span>{entries.length} reports</span>
        <span>{eligible} historical eligible</span>
        <span>{merged} merged PRs</span>
      </div>
    </section>
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
    <StaticEffectCard className={`imagent-landing__contrast-card imagent-landing__contrast-card--${card.tone}`} radius={18}>
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
    </StaticEffectCard>
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
