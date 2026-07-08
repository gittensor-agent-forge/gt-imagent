"use client";

import { useEffect } from "react";

const REVEAL_SELECTOR = "[data-reveal]";
const STAGGER_MS = 90;

export function ScrollReveal() {
  useEffect(() => {
    const elements = Array.from(document.querySelectorAll<HTMLElement>(REVEAL_SELECTOR));
    if (elements.length === 0) {
      return;
    }

    const root = document.documentElement;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    root.classList.add("imagent-reveal-ready");

    elements.forEach((element) => {
      const delay = Number.parseInt(element.dataset.revealDelay ?? "0", 10);
      element.style.setProperty("--reveal-delay", `${Math.max(0, delay) * STAGGER_MS}ms`);

      if (reduceMotion) {
        element.dataset.revealVisible = "true";
      }
    });

    if (reduceMotion) {
      return () => {
        root.classList.remove("imagent-reveal-ready");
      };
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }

          const element = entry.target as HTMLElement;
          element.dataset.revealVisible = "true";
          observer.unobserve(element);
        });
      },
      {
        rootMargin: "0px 0px -12% 0px",
        threshold: 0.14
      }
    );

    elements.forEach((element) => observer.observe(element));

    return () => {
      observer.disconnect();
      root.classList.remove("imagent-reveal-ready");
    };
  }, []);

  return null;
}
