import {
  ArrowRight,
  ArrowUpRight,
  BookOpenText,
  BrainCircuit,
  CheckCircle2,
  GitPullRequestArrow,
  ImageIcon,
  Layers3,
  RadioTower,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { EffectCard } from "@/app/components/EffectCard";
import { LandingBackgroundFx } from "@/app/components/LandingBackgroundFx";
import { ScrollReveal } from "@/app/components/ScrollReveal";
import { IMAGENT_GENERATION_MODEL_NAME } from "@/lib/models";

export const metadata: Metadata = {
  title: "Whitepaper | Imagent",
  description: "The Imagent research thesis: build generation context before the image, then prove the gain in public.",
  alternates: {
    canonical: "/whitepaper"
  },
  openGraph: {
    title: "Whitepaper | Imagent",
    description: "The Imagent research thesis: build generation context before the image, then prove the gain in public.",
    url: "/whitepaper"
  }
};

const trajectory: Array<{
  artifact: string;
  copy: string;
  icon: ReactNode;
  index: string;
  title: string;
}> = [
  {
    artifact: "intent map",
    copy: "Interpret the request as partial context, not a finished image prompt.",
    icon: <ImageIcon size={18} />,
    index: "01",
    title: "Read The Request"
  },
  {
    artifact: "generation plan",
    copy: "Identify the visual structure, constraints, facts, and unanswered questions that matter.",
    icon: <Workflow size={18} />,
    index: "02",
    title: "Plan The Context"
  },
  {
    artifact: "grounded evidence",
    copy: "Resolve missing context with reasoning, search, memory, assets, and feedback when available.",
    icon: <Search size={18} />,
    index: "03",
    title: "Ground The Plan"
  },
  {
    artifact: "model-ready prompt",
    copy: "Construct a deliberate generation instruction for the fixed image model.",
    icon: <Sparkles size={18} />,
    index: "04",
    title: "Generate Deliberately"
  },
  {
    artifact: "scored trajectory",
    copy: "Preserve the result and its evidence so the strategy can be critiqued, benchmarked, and improved.",
    icon: <ShieldCheck size={18} />,
    index: "05",
    title: "Evaluate The Work"
  }
];

const proofSteps = [
  ["01", "Submit", "A contributor proposes one focused agent strategy in a pull request."],
  ["02", "Benchmark", "The same model and benchmark evaluate the candidate against the current winner."],
  ["03", "Clear The Gate", "Only a measurable improvement above the round threshold is promotion eligible."],
  ["04", "Archive", "The winner becomes last_winner and the public history remains available for the next round."]
] as const;

export default function WhitepaperPage() {
  return (
    <div className="imagent-whitepaper">
      <LandingBackgroundFx />
      <ScrollReveal />

      <section className="imagent-whitepaper__masthead" aria-labelledby="whitepaper-title">
        <div className="imagent-whitepaper__masthead-copy" data-reveal="fade-right">
          <span className="imagent-whitepaper__eyebrow"><span /> Imagent Research Note · v1.0</span>
          <p className="imagent-whitepaper__issue">A public thesis for image-generation agents</p>
          <h1 id="whitepaper-title">
            Build The Context
            <em>Before The Image</em>
          </h1>
          <p className="imagent-whitepaper__lede">
            Imagent treats a generation request as the beginning of an agent trajectory. The work is to
            construct the context an image model actually needs, then prove that the resulting strategy is better.
          </p>
          <div className="imagent-whitepaper__actions">
            <a className="imagent-whitepaper__action imagent-whitepaper__action--primary" href="#context-gap">
              Read The Thesis <ArrowRight size={17} />
            </a>
            <Link className="imagent-whitepaper__action imagent-whitepaper__action--secondary" href="/generation">
              Test Generation <ArrowUpRight size={17} />
            </Link>
          </div>
        </div>

        <EffectCard animated className="imagent-whitepaper__source-card" fillOpacity={0.2} glowIntensity={0.76} radius={28}>
          <aside className="imagent-whitepaper__source">
            <div className="imagent-whitepaper__source-topline">
              <span><BookOpenText size={15} /> Research Basis</span>
              <span>01 / 01</span>
            </div>
            <div className="imagent-whitepaper__source-title">
              <span>Paper</span>
              <strong>Qwen-Image-Agent</strong>
              <p>Bridging the Context Gap in Real-World Image Generation</p>
            </div>
            <div className="imagent-whitepaper__source-insight">
              <span>What Imagent Carries Forward</span>
              <p><strong>Plan</strong> the missing context. <strong>Ground</strong> the useful evidence. <strong>Measure</strong> the result.</p>
            </div>
            <a href="https://arxiv.org/abs/2606.26907" rel="noreferrer" target="_blank">
              Read The Research <ArrowUpRight size={15} />
            </a>
          </aside>
        </EffectCard>
      </section>

      <section className="imagent-whitepaper__protocol" aria-label="Imagent research protocol">
        <span><ImageIcon size={15} /> Fixed Image Model <strong>{IMAGENT_GENERATION_MODEL_NAME}</strong></span>
        <span><RadioTower size={15} /> Open Intelligence Market <strong>Gittensor SN74</strong></span>
        <span><GitPullRequestArrow size={15} /> Public Evidence <strong>PRs, Reports, Winner History</strong></span>
      </section>

      <section className="imagent-whitepaper__context" id="context-gap" aria-labelledby="context-gap-title" data-reveal="fade-up">
        <div className="imagent-whitepaper__section-intro">
          <span className="imagent-whitepaper__section-label">01 / The Problem</span>
          <h2 id="context-gap-title">The Prompt Is Often Not The Whole Story</h2>
          <p>
            Real requests can be underspecified, implicit, or dependent on knowledge that is not present in the text.
            The Context Gap is the distance between the context supplied by a user and the context required for a reliable generation.
          </p>
        </div>

        <div className="imagent-whitepaper__context-flow">
          <article className="imagent-whitepaper__context-panel imagent-whitepaper__context-panel--input">
            <span className="imagent-whitepaper__panel-label">What The User Gives</span>
            <p className="imagent-whitepaper__quoted-request">“Create a launch poster for our benchmark winner.”</p>
            <ul>
              <li><CheckCircle2 size={14} /> Intent</li>
              <li><CheckCircle2 size={14} /> A broad outcome</li>
              <li><span /> Missing hierarchy, facts, style, and constraints</li>
            </ul>
          </article>

          <div className="imagent-whitepaper__context-bridge" aria-label="The Context Gap">
            <span>Context Gap</span>
            <div><i /><i /><i /><i /></div>
            <small>Agent work happens here</small>
          </div>

          <article className="imagent-whitepaper__context-panel imagent-whitepaper__context-panel--generation">
            <span className="imagent-whitepaper__panel-label">What The Model Needs</span>
            <p className="imagent-whitepaper__generation-context">A structured visual brief with objective, audience, composition, copy, brand constraints, and relevant evidence.</p>
            <ul>
              <li><CheckCircle2 size={14} /> Grounded facts</li>
              <li><CheckCircle2 size={14} /> Explicit visual decisions</li>
              <li><CheckCircle2 size={14} /> A model-ready generation plan</li>
            </ul>
          </article>
        </div>

        <div className="imagent-whitepaper__context-note">
          <BrainCircuit size={18} />
          <p><strong>Imagent&apos;s research question:</strong> can a better trajectory close this gap while holding the image model constant?</p>
        </div>
      </section>

      <section className="imagent-whitepaper__trajectory" aria-labelledby="trajectory-title" data-reveal="fade-up">
        <div className="imagent-whitepaper__trajectory-head">
          <div className="imagent-whitepaper__section-intro">
            <span className="imagent-whitepaper__section-label">02 / The Method</span>
            <h2 id="trajectory-title">
              A Generation Is A Trace
              <br />
              Not A One-Shot
            </h2>
          </div>
          <p>
            Qwen-Image-Agent frames the agent around planning and grounding. Imagent keeps the same direction visible as a trace that contributors can improve and the benchmark can inspect.
          </p>
        </div>

        <ol className="imagent-whitepaper__trajectory-list">
          {trajectory.map((step) => (
            <li key={step.index}>
              <span className="imagent-whitepaper__trajectory-index">{step.index}</span>
              <span className="imagent-whitepaper__trajectory-icon">{step.icon}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.copy}</p>
              </div>
              <span className="imagent-whitepaper__trajectory-artifact">{step.artifact}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="imagent-whitepaper__boundary" aria-labelledby="boundary-title" data-reveal="fade-up">
        <div className="imagent-whitepaper__boundary-copy">
          <span className="imagent-whitepaper__section-label">03 / The System</span>
          <h2 id="boundary-title">The <em>Agent</em> Is The Variable</h2>
          <p>
            Every candidate is evaluated against the same model, runtime contract, and benchmark. Strategy is the single deliberate variable, so every reported gain has a clear cause.
          </p>
        </div>

        <div className="imagent-whitepaper__boundary-map">
          <div className="imagent-whitepaper__boundary-heading">
            <span>Contributor-Controlled</span>
            <span>Held Constant</span>
          </div>
          <div className="imagent-whitepaper__boundary-grid">
            <EffectCard className="imagent-whitepaper__agent-surface" fillOpacity={0.16} glareOpacity={0.1} glowIntensity={0.58} radius={22}>
              <div>
                <span>Agent Strategy</span>
                <strong>Plan · Reason · Ground · Critique</strong>
                <p>Contributors improve the code that decides what context to build and how to use it.</p>
              </div>
            </EffectCard>

            <div className="imagent-whitepaper__boundary-lock" aria-hidden="true">
              <span />
              <small>Evaluation Boundary</small>
            </div>

            <div className="imagent-whitepaper__fixed-surface">
              <article>
                <ImageIcon size={17} />
                <span>Generation Model</span>
                <strong>{IMAGENT_GENERATION_MODEL_NAME}</strong>
              </article>
              <article>
                <Layers3 size={17} />
                <span>Runtime Contract</span>
                <strong>Artifacts, traces, OpenRouter invocation</strong>
              </article>
              <article>
                <ShieldCheck size={17} />
                <span>Benchmark Proof</span>
                <strong>Score, latency, cost, policy, baseline delta</strong>
              </article>
            </div>
          </div>
          <div className="imagent-whitepaper__boundary-output">
            <RadioTower size={17} />
            <span>Public Output</span>
            <strong>Benchmark report → leaderboard → winner archive</strong>
          </div>
        </div>
      </section>

      <section className="imagent-whitepaper__proof" aria-labelledby="proof-title" data-reveal="fade-up">
        <div className="imagent-whitepaper__proof-intro">
          <span className="imagent-whitepaper__section-label">04 / The Proof Loop</span>
          <h2 id="proof-title">A Better Agent Must Earn Its Place</h2>
          <p>
            The project is not optimized for a private demo. Public rounds turn proposed strategies into comparable evidence, while preserving non-winning work for the next iteration.
          </p>
        </div>

        <ol className="imagent-whitepaper__proof-track">
          {proofSteps.map(([index, title, copy]) => (
            <li key={index}>
              <span>{index}</span>
              <div>
                <h3>{title}</h3>
                <p>{copy}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="imagent-whitepaper__thesis" aria-labelledby="thesis-title" data-reveal="scale">
        <div className="imagent-whitepaper__thesis-copy">
          <span className="imagent-whitepaper__section-label"><Sparkles size={15} /> The v1.0 Claim</span>
          <h2 id="thesis-title">Better Reasoning Should Make The Same Model Produce Better Images</h2>
          <p>
            Imagent&apos;s first falsifiable milestone is clear: an agent using Gemini 3.1 Flash Image should consistently outperform direct Gemini 3.1 Flash Image usage. If it does, the lift comes from planning, context construction, orchestration, and evaluation.
          </p>
        </div>
        <div className="imagent-whitepaper__thesis-actions">
          <span className="imagent-whitepaper__thesis-action-label">Follow The Evidence</span>
          <Link className="imagent-whitepaper__action imagent-whitepaper__action--primary" href="/leaderboard">
            See Benchmark Evidence <GitPullRequestArrow size={17} />
          </Link>
          <Link className="imagent-whitepaper__action imagent-whitepaper__action--secondary" href="/generation">
            Try The Agent <ArrowRight size={17} />
          </Link>
        </div>
      </section>
    </div>
  );
}
