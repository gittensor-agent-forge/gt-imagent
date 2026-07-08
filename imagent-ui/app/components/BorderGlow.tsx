"use client";

import { useCallback, useEffect, useRef, type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import "./BorderGlow.css";

type BorderGlowProps = {
  animated?: boolean;
  backgroundColor?: string;
  borderRadius?: number;
  children: ReactNode;
  className?: string;
  colors?: string[];
  coneSpread?: number;
  edgeSensitivity?: number;
  fillOpacity?: number;
  glowColor?: string;
  glowIntensity?: number;
  glowRadius?: number;
};

const gradientPositions = ["80% 55%", "69% 34%", "8% 6%", "41% 38%", "86% 85%", "82% 18%", "51% 4%"];
const gradientKeys = [
  "--gradient-one",
  "--gradient-two",
  "--gradient-three",
  "--gradient-four",
  "--gradient-five",
  "--gradient-six",
  "--gradient-seven"
] as const;
const colorMap = [0, 1, 2, 0, 1, 2, 1];

function parseHsl(hsl: string) {
  const match = hsl.match(/([\d.]+)\s*([\d.]+)%?\s*([\d.]+)%?/);
  if (!match) {
    return { h: 40, l: 80, s: 80 };
  }
  return { h: Number.parseFloat(match[1]), l: Number.parseFloat(match[3]), s: Number.parseFloat(match[2]) };
}

function buildGlowVars(glowColor: string, intensity: number) {
  const { h, l, s } = parseHsl(glowColor);
  const base = `${h}deg ${s}% ${l}%`;
  const opacities = [100, 60, 50, 40, 30, 20, 10];
  const keys = ["", "-60", "-50", "-40", "-30", "-20", "-10"];
  return opacities.reduce<Record<string, string>>((vars, opacity, index) => {
    vars[`--glow-color${keys[index]}`] = `hsl(${base} / ${Math.min(opacity * intensity, 100)}%)`;
    return vars;
  }, {});
}

function buildGradientVars(colors: string[]) {
  const vars = gradientKeys.reduce<Record<string, string>>((acc, key, index) => {
    const color = colors[Math.min(colorMap[index], colors.length - 1)];
    acc[key] = `radial-gradient(at ${gradientPositions[index]}, ${color} 0px, transparent 50%)`;
    return acc;
  }, {});
  vars["--gradient-base"] = `linear-gradient(${colors[0]} 0 100%)`;
  return vars;
}

function easeOutCubic(value: number) {
  return 1 - Math.pow(1 - value, 3);
}

function easeInCubic(value: number) {
  return value * value * value;
}

function animateValue({
  delay = 0,
  duration = 1000,
  ease = easeOutCubic,
  end = 100,
  onEnd,
  onUpdate,
  start = 0
}: {
  delay?: number;
  duration?: number;
  ease?: (value: number) => number;
  end?: number;
  onEnd?: () => void;
  onUpdate: (value: number) => void;
  start?: number;
}) {
  const startedAt = performance.now() + delay;
  let frameId: number | null = null;
  let cancelled = false;

  function tick() {
    if (cancelled) {
      return;
    }

    const elapsed = performance.now() - startedAt;
    const progress = Math.min(elapsed / duration, 1);
    onUpdate(start + (end - start) * ease(progress));
    if (progress < 1) {
      frameId = requestAnimationFrame(tick);
      return;
    }
    onEnd?.();
  }

  const timeoutId = window.setTimeout(() => {
    frameId = requestAnimationFrame(tick);
  }, delay);

  return () => {
    cancelled = true;
    window.clearTimeout(timeoutId);
    if (frameId !== null) {
      cancelAnimationFrame(frameId);
    }
  };
}

export function BorderGlow({
  animated = false,
  backgroundColor,
  borderRadius = 22,
  children,
  className = "",
  colors = ["#00e2fb", "#0171f9", "#85f5ad"],
  coneSpread = 24,
  edgeSensitivity = 24,
  fillOpacity = 0.28,
  glowColor = "188 100 72",
  glowIntensity = 0.9,
  glowRadius = 36
}: BorderGlowProps) {
  const cardRef = useRef<HTMLDivElement>(null);

  const getCenter = useCallback((element: HTMLElement) => {
    const { height, width } = element.getBoundingClientRect();
    return [width / 2, height / 2];
  }, []);

  const getEdgeProximity = useCallback(
    (element: HTMLElement, x: number, y: number) => {
      const [centerX, centerY] = getCenter(element);
      const dx = x - centerX;
      const dy = y - centerY;
      const kx = dx === 0 ? Infinity : centerX / Math.abs(dx);
      const ky = dy === 0 ? Infinity : centerY / Math.abs(dy);
      return Math.min(Math.max(1 / Math.min(kx, ky), 0), 1);
    },
    [getCenter]
  );

  const getCursorAngle = useCallback(
    (element: HTMLElement, x: number, y: number) => {
      const [centerX, centerY] = getCenter(element);
      const dx = x - centerX;
      const dy = y - centerY;
      if (dx === 0 && dy === 0) {
        return 0;
      }
      const degrees = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
      return degrees < 0 ? degrees + 360 : degrees;
    },
    [getCenter]
  );

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const card = cardRef.current;
      if (!card) {
        return;
      }

      const rect = card.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;

      card.style.setProperty("--edge-proximity", `${(getEdgeProximity(card, x, y) * 100).toFixed(3)}`);
      card.style.setProperty("--cursor-angle", `${getCursorAngle(card, x, y).toFixed(3)}deg`);
    },
    [getCursorAngle, getEdgeProximity]
  );

  useEffect(() => {
    if (!animated || !cardRef.current) {
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const card = cardRef.current;
    const cleanups: Array<() => void> = [];
    const angleStart = 110;
    const angleEnd = 465;
    card.classList.add("sweep-active");
    card.style.setProperty("--cursor-angle", `${angleStart}deg`);

    cleanups.push(
      animateValue({ duration: 500, onUpdate: (value) => card.style.setProperty("--edge-proximity", `${value}`) }),
      animateValue({
        duration: 1500,
        ease: easeInCubic,
        end: 50,
        onUpdate: (value) => {
          card.style.setProperty("--cursor-angle", `${(angleEnd - angleStart) * (value / 100) + angleStart}deg`);
        }
      }),
      animateValue({
        delay: 1500,
        duration: 2250,
        ease: easeOutCubic,
        end: 100,
        start: 50,
        onUpdate: (value) => {
          card.style.setProperty("--cursor-angle", `${(angleEnd - angleStart) * (value / 100) + angleStart}deg`);
        }
      }),
      animateValue({
        delay: 2500,
        duration: 1500,
        ease: easeInCubic,
        onEnd: () => card.classList.remove("sweep-active"),
        onUpdate: (value) => card.style.setProperty("--edge-proximity", `${value}`),
        start: 100
      })
    );

    return () => {
      cleanups.forEach((cleanup) => cleanup());
      card.classList.remove("sweep-active");
    };
  }, [animated]);

  const style = {
    "--border-radius": `${borderRadius}px`,
    ...(backgroundColor ? { "--card-bg": backgroundColor } : {}),
    "--cone-spread": coneSpread,
    "--edge-sensitivity": edgeSensitivity,
    "--fill-opacity": fillOpacity,
    "--glow-padding": `${glowRadius}px`,
    ...buildGlowVars(glowColor, glowIntensity),
    ...buildGradientVars(colors)
  } as CSSProperties;

  return (
    <div className={`border-glow-card ${className}`} onPointerMove={handlePointerMove} ref={cardRef} style={style}>
      <span className="edge-light" />
      <div className="border-glow-inner">{children}</div>
    </div>
  );
}
