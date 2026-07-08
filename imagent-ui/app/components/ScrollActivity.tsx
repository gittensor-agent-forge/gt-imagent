"use client";

import { useEffect } from "react";

type Axis = "vertical" | "horizontal";

type Metrics = {
  maxScroll: number;
  thumbSize: number;
  trackSize: number;
};

type ScrollbarRecord = {
  element: HTMLElement | null;
  horizontal: HTMLButtonElement;
  horizontalMetrics: Metrics | null;
  hideTimer: number;
  vertical: HTMLButtonElement;
  verticalMetrics: Metrics | null;
};

const EDGE_SIZE = 22;
const HIDE_DELAY_MS = 1500;
const MIN_THUMB_SIZE = 42;
const TRACK_INSET = 4;
const TARGET_SELECTOR = ".custom-scrollbar, .leaderboard-table-wrap";

export function ScrollActivity() {
  useEffect(() => {
    const records = new Map<HTMLElement | null, ScrollbarRecord>();
    let frame = 0;

    function createThumb(axis: Axis) {
      const thumb = document.createElement("button");
      thumb.type = "button";
      thumb.className = `custom-scrollbar-thumb ${axis}`;
      thumb.tabIndex = -1;
      thumb.setAttribute("aria-hidden", "true");
      document.body.appendChild(thumb);
      return thumb;
    }

    function recordFor(element: HTMLElement | null) {
      const existing = records.get(element);
      if (existing) {
        return existing;
      }
      const record: ScrollbarRecord = {
        element,
        hideTimer: 0,
        horizontal: createThumb("horizontal"),
        horizontalMetrics: null,
        vertical: createThumb("vertical"),
        verticalMetrics: null
      };
      attachDrag(record, "vertical");
      attachDrag(record, "horizontal");
      records.set(element, record);
      return record;
    }

    function refreshTargets() {
      recordFor(null);
      document.querySelectorAll<HTMLElement>(TARGET_SELECTOR).forEach((element) => recordFor(element));
      records.forEach((record, element) => {
        if (element && !document.body.contains(element)) {
          record.vertical.remove();
          record.horizontal.remove();
          if (record.hideTimer) {
            window.clearTimeout(record.hideTimer);
          }
          records.delete(element);
        }
      });
      scheduleUpdate();
    }

    function scheduleUpdate() {
      if (frame) {
        return;
      }
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        records.forEach(updateRecord);
      });
    }

    function show(record: ScrollbarRecord) {
      record.vertical.classList.add("visible");
      record.horizontal.classList.add("visible");
      if (record.hideTimer) {
        window.clearTimeout(record.hideTimer);
      }
      record.hideTimer = window.setTimeout(() => {
        record.vertical.classList.remove("visible");
        record.horizontal.classList.remove("visible");
      }, HIDE_DELAY_MS);
      scheduleUpdate();
    }

    function onScroll(event: Event) {
      const target = event.target;
      if (target === document || target === window) {
        show(recordFor(null));
        return;
      }
      if (target instanceof HTMLElement) {
        const scroller = target.matches(TARGET_SELECTOR) ? target : target.closest<HTMLElement>(TARGET_SELECTOR);
        if (scroller) {
          show(recordFor(scroller));
        }
      }
    }

    function onWheel(event: WheelEvent) {
      const target = scrollTargetFromPoint(event.clientX, event.clientY);
      if (target !== undefined) {
        show(recordFor(target));
      }
    }

    function onPointerMove(event: PointerEvent) {
      const hovered = scrollTargetFromPoint(event.clientX, event.clientY);

      if (hovered instanceof HTMLElement) {
        const rect = hovered.getBoundingClientRect();
        const nearVerticalEdge = hovered.scrollHeight > hovered.clientHeight && event.clientX >= rect.right - EDGE_SIZE;
        const nearHorizontalEdge = hovered.scrollWidth > hovered.clientWidth && event.clientY >= rect.bottom - EDGE_SIZE;
        if (nearVerticalEdge || nearHorizontalEdge) {
          show(recordFor(hovered));
        }
      } else if (document.documentElement.scrollHeight > window.innerHeight && event.clientX >= window.innerWidth - EDGE_SIZE) {
        show(recordFor(null));
      }
    }

    function onTouchMove(event: TouchEvent) {
      const touch = event.touches[0];
      if (!touch) {
        return;
      }
      const target = scrollTargetFromPoint(touch.clientX, touch.clientY);
      if (target !== undefined) {
        show(recordFor(target));
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      const scrollKeys = ["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", "Space"];
      if (!scrollKeys.includes(event.code) && !scrollKeys.includes(event.key)) {
        return;
      }
      const focused = document.activeElement?.closest<HTMLElement>(TARGET_SELECTOR);
      if (focused && isScrollable(focused)) {
        show(recordFor(focused));
        return;
      }
      show(recordFor(null));
    }

    function scrollTargetFromPoint(x: number, y: number) {
      const element = document.elementFromPoint(x, y);
      const hovered = element?.closest<HTMLElement>(TARGET_SELECTOR);
      if (hovered && isScrollable(hovered)) {
        return hovered;
      }
      if (document.documentElement.scrollHeight > window.innerHeight) {
        return null;
      }
      return undefined;
    }

    function updateRecord(record: ScrollbarRecord) {
      updateVertical(record);
      updateHorizontal(record);
    }

    function updateVertical(record: ScrollbarRecord) {
      const element = record.element;
      const thumb = record.vertical;
      const maxScroll = element ? element.scrollHeight - element.clientHeight : document.documentElement.scrollHeight - window.innerHeight;
      if (maxScroll <= 1) {
        thumb.classList.remove("visible");
        record.verticalMetrics = null;
        return;
      }

      const rect = element?.getBoundingClientRect();
      const header = document.querySelector<HTMLElement>(".app-header");
      const top = rect ? Math.max(rect.top + TRACK_INSET, TRACK_INSET) : Math.max((header?.getBoundingClientRect().bottom || 0) + TRACK_INSET, TRACK_INSET);
      const bottom = rect ? Math.min(rect.bottom - TRACK_INSET, window.innerHeight - TRACK_INSET) : window.innerHeight - TRACK_INSET;
      const trackSize = Math.max(0, bottom - top);
      if (trackSize < MIN_THUMB_SIZE) {
        thumb.classList.remove("visible");
        record.verticalMetrics = null;
        return;
      }

      const viewportSize = element ? element.clientHeight : window.innerHeight;
      const scrollSize = element ? element.scrollHeight : document.documentElement.scrollHeight;
      const scrollTop = clamp(element ? element.scrollTop : window.scrollY, 0, maxScroll);
      const thumbSize = Math.max(MIN_THUMB_SIZE, Math.min(trackSize, (viewportSize / scrollSize) * trackSize));
      const thumbTop = clamp(top + (scrollTop / maxScroll) * (trackSize - thumbSize), top, bottom - thumbSize);
      const left = rect ? rect.right - 12 : window.innerWidth - 12;

      thumb.style.height = `${thumbSize}px`;
      thumb.style.transform = `translate3d(${Math.round(left)}px, ${Math.round(thumbTop)}px, 0)`;
      record.verticalMetrics = { maxScroll, thumbSize, trackSize };
    }

    function updateHorizontal(record: ScrollbarRecord) {
      const element = record.element;
      const thumb = record.horizontal;
      if (!element) {
        thumb.classList.remove("visible");
        record.horizontalMetrics = null;
        return;
      }

      const maxScroll = element.scrollWidth - element.clientWidth;
      if (maxScroll <= 1) {
        thumb.classList.remove("visible");
        record.horizontalMetrics = null;
        return;
      }

      const rect = element.getBoundingClientRect();
      const left = Math.max(rect.left + TRACK_INSET, TRACK_INSET);
      const right = Math.min(rect.right - TRACK_INSET, window.innerWidth - TRACK_INSET);
      const trackSize = Math.max(0, right - left);
      if (trackSize < MIN_THUMB_SIZE) {
        thumb.classList.remove("visible");
        record.horizontalMetrics = null;
        return;
      }

      const thumbSize = Math.max(MIN_THUMB_SIZE, Math.min(trackSize, (element.clientWidth / element.scrollWidth) * trackSize));
      const scrollLeft = clamp(element.scrollLeft, 0, maxScroll);
      const thumbLeft = clamp(left + (scrollLeft / maxScroll) * (trackSize - thumbSize), left, right - thumbSize);
      const top = rect.bottom - 12;

      thumb.style.width = `${thumbSize}px`;
      thumb.style.transform = `translate3d(${Math.round(thumbLeft)}px, ${Math.round(top)}px, 0)`;
      record.horizontalMetrics = { maxScroll, thumbSize, trackSize };
    }

    function attachDrag(record: ScrollbarRecord, axis: Axis) {
      const thumb = axis === "vertical" ? record.vertical : record.horizontal;
      thumb.addEventListener("pointerdown", (event) => {
        const metrics = axis === "vertical" ? record.verticalMetrics : record.horizontalMetrics;
        if (!metrics) {
          return;
        }
        event.preventDefault();
        thumb.setPointerCapture(event.pointerId);
        thumb.classList.add("dragging", "visible");
        const startPointer = axis === "vertical" ? event.clientY : event.clientX;
        const startScroll = getScroll(record.element, axis);
        const move = (moveEvent: PointerEvent) => {
          const currentPointer = axis === "vertical" ? moveEvent.clientY : moveEvent.clientX;
          const delta = currentPointer - startPointer;
          const trackDelta = Math.max(1, metrics.trackSize - metrics.thumbSize);
          setScroll(record.element, axis, clamp(startScroll + (delta / trackDelta) * metrics.maxScroll, 0, metrics.maxScroll));
          show(record);
        };
        const up = () => {
          thumb.classList.remove("dragging");
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", up);
          show(record);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up, { once: true });
      });
    }

    function getScroll(element: HTMLElement | null, axis: Axis) {
      if (!element) {
        return axis === "vertical" ? window.scrollY : window.scrollX;
      }
      return axis === "vertical" ? element.scrollTop : element.scrollLeft;
    }

    function setScroll(element: HTMLElement | null, axis: Axis, value: number) {
      if (!element) {
        if (axis === "vertical") {
          window.scrollTo({ top: value, left: window.scrollX });
        } else {
          window.scrollTo({ top: window.scrollY, left: value });
        }
        return;
      }
      if (axis === "vertical") {
        element.scrollTop = value;
      } else {
        element.scrollLeft = value;
      }
    }

    function onResize() {
      refreshTargets();
    }

    const observer = new MutationObserver(refreshTargets);
    observer.observe(document.body, { childList: true, subtree: true });
    refreshTargets();

    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("wheel", onWheel, { passive: true });
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onResize);

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onResize);
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
      records.forEach((record) => {
        if (record.hideTimer) {
          window.clearTimeout(record.hideTimer);
        }
        record.vertical.remove();
        record.horizontal.remove();
      });
    };
  }, []);

  return null;
}

function isScrollable(element: HTMLElement) {
  return element.scrollHeight > element.clientHeight || element.scrollWidth > element.clientWidth;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
