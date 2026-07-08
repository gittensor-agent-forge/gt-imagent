"use client";

import { startTransition, useState } from "react";
import {
  BrainCircuit,
  CheckCircle2,
  Gauge,
  GitMerge,
  Search,
  WandSparkles
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { EffectCard } from "@/app/components/EffectCard";

type StepStatus = "active" | "complete" | "queued";

type AgentStep = {
  copy: string;
  detail: string;
  icon: LucideIcon;
  title: string;
};

const agentSteps: AgentStep[] = [
  {
    copy: "Read user intent",
    detail: "Constraints and missing context are extracted",
    icon: Search,
    title: "Interpret"
  },
  {
    copy: "Build trajectory",
    detail: "Tools and checks are selected",
    icon: BrainCircuit,
    title: "Plan"
  },
  {
    copy: "Call image model",
    detail: "Gemini renders from the structured prompt",
    icon: WandSparkles,
    title: "Generate"
  },
  {
    copy: "Critique output",
    detail: "Alignment quality and evidence are measured",
    icon: Gauge,
    title: "Score"
  },
  {
    copy: "Update winner",
    detail: "Best passing strategy becomes reference",
    icon: GitMerge,
    title: "Promote"
  }
];

export function AgentStepper() {
  const [activeIndex, setActiveIndex] = useState(2);

  function selectStep(index: number) {
    startTransition(() => {
      setActiveIndex(index);
    });
  }

  return (
    <div className="imagent-landing__stepper" aria-label="Agent trajectory steps" role="group">
      <div className="imagent-landing__stepper-track" aria-label="Select agent trajectory step" data-reveal="fade-up" role="group">
        {agentSteps.map((step, index) => {
          const status = getStepStatus(index, activeIndex);

          return (
            <div className="imagent-landing__stepper-node" key={step.title}>
              <button
                aria-current={status === "active" ? "step" : undefined}
                aria-label={`Show ${step.title} step`}
                className={`imagent-landing__stepper-dot imagent-landing__stepper-dot--${status}`}
                onClick={() => selectStep(index)}
                type="button"
              >
                {status === "complete" ? <CheckCircle2 size={16} /> : <span>{index + 1}</span>}
              </button>
              {index < agentSteps.length - 1 ? (
                <span
                  className={`imagent-landing__stepper-connector ${
                    index < activeIndex ? "imagent-landing__stepper-connector--filled" : ""
                  }`}
                />
              ) : null}
            </div>
          );
        })}
      </div>
      <ol className="imagent-landing__stepper-grid" aria-label="Trajectory step details">
        {agentSteps.map((step, index) => {
          const Icon = step.icon;
          const status = getStepStatus(index, activeIndex);

          return (
            <li className="imagent-landing__step-card-item" data-reveal="fade-up" data-reveal-delay={index + 1} key={step.title}>
              <EffectCard
                animated={status === "active"}
                className={`imagent-landing__step-card imagent-landing__step-card--${status}`}
                glareOpacity={status === "active" ? 0.16 : 0.1}
                radius={20}
              >
                <button
                  aria-current={status === "active" ? "step" : undefined}
                  className="imagent-landing__step-card-button"
                  onClick={() => selectStep(index)}
                  type="button"
                >
                  <div className="imagent-landing__step-card-head">
                    <div>
                      <Icon size={18} />
                      <span>{String(index + 1).padStart(2, "0")}</span>
                    </div>
                    <span className={`imagent-landing__step-card-status imagent-landing__step-card-status--${status}`}>
                      {formatStepStatus(status)}
                    </span>
                  </div>
                  <h3>{step.title}</h3>
                  <p>{step.copy}</p>
                  <small>{step.detail}</small>
                </button>
              </EffectCard>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function getStepStatus(index: number, activeIndex: number): StepStatus {
  if (index < activeIndex) {
    return "complete";
  }
  if (index === activeIndex) {
    return "active";
  }
  return "queued";
}

function formatStepStatus(status: StepStatus) {
  if (status === "complete") {
    return "Done";
  }
  if (status === "active") {
    return "Current";
  }
  return "Next";
}
