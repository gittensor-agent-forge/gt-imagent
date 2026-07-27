"use client";

import { useEffect, useRef } from "react";

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
        root.style.setProperty("--imagent-page-pointer-x", pointerRef.current.x);
        root.style.setProperty("--imagent-page-pointer-y", pointerRef.current.y);
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
    <div className="imagent-page-background-fx" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}
