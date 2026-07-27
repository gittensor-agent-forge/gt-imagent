"use client";

import type { ReactNode } from "react";
import { BorderGlow } from "@/app/components/BorderGlow";
import { GlareHover } from "@/app/components/GlareHover";

type EffectCardProps = {
  animated?: boolean;
  children: ReactNode;
  className?: string;
  coneSpread?: number;
  edgeSensitivity?: number;
  fillOpacity?: number;
  glareOpacity?: number;
  glowIntensity?: number;
  glowRadius?: number;
  radius?: number;
};

export function EffectCard({
  animated = false,
  children,
  className = "",
  coneSpread,
  edgeSensitivity,
  fillOpacity,
  glareOpacity = 0.16,
  glowIntensity,
  glowRadius,
  radius = 22
}: EffectCardProps) {
  return (
    <BorderGlow
      animated={animated}
      borderRadius={radius}
      className={`imagent-effect-card ${className}`}
      coneSpread={coneSpread}
      edgeSensitivity={edgeSensitivity}
      fillOpacity={fillOpacity}
      glowIntensity={glowIntensity}
      glowRadius={glowRadius}
    >
      <GlareHover borderRadius="inherit" className="imagent-effect-card__glare" glareOpacity={glareOpacity}>
        <div className="imagent-effect-card__content">{children}</div>
      </GlareHover>
    </BorderGlow>
  );
}
