"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { BorderGlow } from "@/app/components/BorderGlow";
import { GlareHover } from "@/app/components/GlareHover";

type EffectCardProps = {
  animated?: boolean;
  children: ReactNode;
  className?: string;
  glareOpacity?: number;
  radius?: number;
};

export function EffectCard({
  animated = false,
  children,
  className = "",
  glareOpacity = 0.16,
  radius = 22
}: EffectCardProps) {
  return (
    <BorderGlow animated={animated} borderRadius={radius} className={`imagent-effect-card ${className}`}>
      <GlareHover borderRadius="inherit" className="imagent-effect-card__glare" glareOpacity={glareOpacity}>
        <div className="imagent-effect-card__content">{children}</div>
      </GlareHover>
    </BorderGlow>
  );
}

export function LandingBackgroundFx() {
  const frameRef = useRef<number | null>(null);
  const pointerRef = useRef({ x: "70vw", y: "22vh" });

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const root = document.documentElement;

    const handlePointerMove = (event: PointerEvent) => {
      pointerRef.current = {
        x: `${event.clientX}px`,
        y: `${event.clientY}px`
      };

      if (frameRef.current !== null) {
        return;
      }

      frameRef.current = requestAnimationFrame(() => {
        root.style.setProperty("--landing-pointer-x", pointerRef.current.x);
        root.style.setProperty("--landing-pointer-y", pointerRef.current.y);
        frameRef.current = null;
      });
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, []);

  return (
    <div className="imagent-landing__background-fx" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}
