"use client";

import type { CSSProperties, ReactNode } from "react";
import "./GlareHover.css";

type GlareHoverProps = {
  background?: string;
  borderColor?: string;
  borderRadius?: string;
  children: ReactNode;
  className?: string;
  glareAngle?: number;
  glareColor?: string;
  glareOpacity?: number;
  glareSize?: number;
  height?: string;
  playOnce?: boolean;
  style?: CSSProperties;
  transitionDuration?: number;
  width?: string;
};

function toRgba(color: string, opacity: number) {
  const hex = color.replace("#", "");
  if (/^[0-9A-Fa-f]{6}$/.test(hex)) {
    const r = Number.parseInt(hex.slice(0, 2), 16);
    const g = Number.parseInt(hex.slice(2, 4), 16);
    const b = Number.parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  if (/^[0-9A-Fa-f]{3}$/.test(hex)) {
    const r = Number.parseInt(hex[0] + hex[0], 16);
    const g = Number.parseInt(hex[1] + hex[1], 16);
    const b = Number.parseInt(hex[2] + hex[2], 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return color;
}

export function GlareHover({
  background = "transparent",
  borderColor = "transparent",
  borderRadius = "inherit",
  children,
  className = "",
  glareAngle = -32,
  glareColor = "#ffffff",
  glareOpacity = 0.18,
  glareSize = 260,
  height = "100%",
  playOnce = false,
  style = {},
  transitionDuration = 720,
  width = "100%"
}: GlareHoverProps) {
  const vars = {
    "--gh-angle": `${glareAngle}deg`,
    "--gh-bg": background,
    "--gh-border": borderColor,
    "--gh-br": borderRadius,
    "--gh-duration": `${transitionDuration}ms`,
    "--gh-height": height,
    "--gh-rgba": toRgba(glareColor, glareOpacity),
    "--gh-size": `${glareSize}%`,
    "--gh-width": width
  } as CSSProperties;

  return (
    <div className={`glare-hover ${playOnce ? "glare-hover--play-once" : ""} ${className}`} style={{ ...vars, ...style }}>
      {children}
    </div>
  );
}
