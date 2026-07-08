import { ArrowRight, BookOpenText, BrainCircuit, GitPullRequestArrow, Layers3, RadioTower, Search, ShieldCheck, Workflow } from "lucide-react";
import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { IMAGENT_GENERATION_MODEL_NAME } from "@/lib/models";

export const metadata: Metadata = {
  title: "Whitepaper | Imagent",
  description: "Imagent v1.0 thesis for context-aware image-generation agents inspired by Qwen-Image-Agent.",
  alternates: {
    canonical: "/whitepaper"
  },
  openGraph: {
    title: "Whitepaper | Imagent",
    description: "Imagent v1.0 thesis for context-aware image-generation agents inspired by Qwen-Image-Agent.",
    url: "/whitepaper"
  }
};

const principles = [
  {
    title: "Context is the bottleneck",
    copy: "A user prompt is rarely the full generation context. The agent must identify missing structure, facts, constraints, and intent before rendering."
  },
  {
    title: "The model stays fixed",
    copy: `Imagent v1.0 fixes generation to ${IMAGENT_GENERATION_MODEL_NAME} through OpenRouter so benchmark gains come from orchestration, not model switching.`
  },
  {
    title: "Trajectories matter",
    copy: "Final image quality is important, but the long-term research target is the full plan, context, generation, critique, and regeneration path."
  }
];

const architecture = [
  ["Agent", "Contributor-controlled strategy code that plans, reasons, builds prompts, and decides how to use available context."],
  ["Runtime", "Stable execution layer that loads the agent, creates artifacts, invokes OpenRouter, and writes trace metadata."],
  ["Benchmark", "Evaluation suite that scores generated images, cost, latency, policy thresholds, and improvement over the current best."],
  ["Leaderboard", "Public product surface for reports, PR outcomes, winner history, model attribution, and benchmark deltas."]
];

export default function WhitepaperPage() {
  return (
    <div className="whitepaper-page">
      <section className="whitepaper-hero">
        <div>
          <span className="page-kicker">Whitepaper · Imagent v1.0 thesis</span>
          <h1>From prompt-to-image to image-generation agents.</h1>
          <p>
            Imagent applies the agentic image-generation direction introduced by Qwen-Image-Agent:
            bridge the gap between what a user provides and what an image model needs to generate
            reliably.
          </p>
          <div className="hero-actions">
            <a className="secondary-action" href="https://arxiv.org/abs/2606.26907" target="_blank" rel="noreferrer">
              Research reference <BookOpenText size={16} />
            </a>
            <Link className="primary-action" href="/generation">
              Test the agent <ArrowRight size={16} />
            </Link>
          </div>
        </div>
        <aside className="paper-citation">
          <span>Research Basis</span>
          <strong>Qwen-Image-Agent</strong>
          <p>
            The paper defines the Context Gap and proposes Context-Aware Planning plus Context
            Grounding across plan, reason, search, memory, and feedback.
          </p>
        </aside>
      </section>

      <section className="paper-section">
        <span className="section-eyebrow">Problem</span>
        <h2>The Context Gap</h2>
        <p>
          Real-world image requests are often underspecified, implicit, or dependent on facts and
          preferences that are not present in the prompt. A direct image call treats the prompt as
          complete. Imagent treats it as partial context.
        </p>
        <div className="principle-grid">
          {principles.map((item) => (
            <article className="principle-card" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="paper-section split">
        <div>
          <span className="section-eyebrow">Method</span>
          <h2>Context-aware planning, then grounded generation.</h2>
          <p>
            The reference agent is intentionally simple, but the research path is clear: plan what
            information is missing, ground that information through reasoning/search/memory/feedback,
            construct a stronger generation prompt, and preserve the full trajectory for evaluation.
          </p>
        </div>
        <div className="method-stack">
          <MethodStep icon={<Workflow size={18} />} title="Plan" copy="Identify layout, constraints, text requirements, and missing context." />
          <MethodStep icon={<BrainCircuit size={18} />} title="Reason" copy="Resolve implicit intent, arithmetic, visual structure, and consistency rules." />
          <MethodStep icon={<Search size={18} />} title="Ground" copy="Use assets, search snapshots, memory, and feedback to complete generation context." />
          <MethodStep icon={<ShieldCheck size={18} />} title="Evaluate" copy="Score final images and eventually evaluate trajectories, not only pixels." />
        </div>
      </section>

      <section className="paper-section">
        <span className="section-eyebrow">Architecture</span>
        <h2>Imagent separates agent strategy from stable runtime.</h2>
        <div className="architecture-grid">
          {architecture.map(([title, copy]) => (
            <article className="architecture-card" key={title}>
              <Layers3 size={18} />
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="paper-section">
        <span className="section-eyebrow">Competition Loop</span>
        <h2>Two daily rounds turn research ideas into measurable software.</h2>
        <div className="round-timeline">
          <RoundStep title="Submit one PR" copy="Contributors change only the agent candidate surface." />
          <RoundStep title="Run benchmark" copy="The benchmark compares scores against the current last winner and threshold." />
          <RoundStep title="Promote winner" copy="The top eligible agent becomes last_winner and is archived under winners." />
          <RoundStep title="Rebase non-winners" copy="Eligible non-winners stay open but must rebase after a winner merges." />
        </div>
      </section>

      <section className="paper-section gittensor-panel">
        <div>
          <span className="section-eyebrow">Gittensor</span>
          <h2>An open intelligence market for image-agent progress.</h2>
          <p>
            Imagent makes Gittensor visible in the product: the website, README, benchmark reports,
            and winner archives all show that Gittensor helps power the contributor loop. The goal is
            to reward measurable agent capability gains rather than one-off demos.
          </p>
        </div>
        <div className="gittensor-mark">
          <RadioTower size={30} />
          <strong>SN74</strong>
          <span>public rounds · benchmark reports · winner archives</span>
        </div>
      </section>

      <section className="paper-section roadmap-panel">
        <span className="section-eyebrow">Roadmap</span>
        <h2>What v1.0 should prove.</h2>
        <p>
          The first milestone is simple and falsifiable: an agent using Gemini 3.1 Flash Image should
          consistently outperform direct Gemini 3.1 Flash Image usage. If that holds, planning,
          orchestration, context construction, and evaluation are creating real leverage.
        </p>
        <div className="hero-actions">
          <Link className="primary-action" href="/leaderboard">
            View benchmark proof <GitPullRequestArrow size={16} />
          </Link>
          <Link className="secondary-action" href="/generation">
            Try generation <ArrowRight size={16} />
          </Link>
        </div>
      </section>
    </div>
  );
}

function MethodStep({ copy, icon, title }: { copy: string; icon: ReactNode; title: string }) {
  return (
    <article className="method-step">
      {icon}
      <div>
        <h3>{title}</h3>
        <p>{copy}</p>
      </div>
    </article>
  );
}

function RoundStep({ copy, title }: { copy: string; title: string }) {
  return (
    <article className="round-step">
      <strong>{title}</strong>
      <p>{copy}</p>
    </article>
  );
}
