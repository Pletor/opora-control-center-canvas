// Který tah se právě čte: IntersectionObserver nad sekcemi tahů (`data-turn`) v posuvné konverzaci.
// Čtecí linka je horních 35 % výšky; aktivní je první tah, který do ní zasahuje. Na samém konci
// konverzace je aktivní poslední tah, i když je krátký a k lince nedosáhne. Volá ho jen Conversation.
import { useEffect, useRef, type RefObject } from "react";

export function useActiveTurn(scroller: RefObject<HTMLElement | null>, anchors: string[], onActive: (anchor: string | null) => void): void {
  const report = useRef(onActive);
  report.current = onActive;
  const key = anchors.join("\n");

  useEffect(() => {
    const root = scroller.current;
    const list = key ? key.split("\n") : [];
    const last = list[list.length - 1] ?? null;
    if (!root || !list.length || typeof IntersectionObserver === "undefined") {
      report.current(last);
      return;
    }
    const visible = new Set<string>();
    const atEnd = () => root.scrollHeight - root.scrollTop - root.clientHeight < 8;
    const pick = () => {
      if (atEnd()) { report.current(last); return; }
      const first = list.find((a) => visible.has(a));
      if (first) report.current(first);
    };
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const anchor = (entry.target as HTMLElement).dataset.turn;
          if (!anchor) continue;
          if (entry.isIntersecting) visible.add(anchor);
          else visible.delete(anchor);
        }
        pick();
      },
      { root, rootMargin: "0px 0px -65% 0px", threshold: 0 },
    );
    root.querySelectorAll<HTMLElement>("[data-turn]").forEach((el) => observer.observe(el));
    const onScroll = () => { if (atEnd()) report.current(last); };
    root.addEventListener("scroll", onScroll, { passive: true });
    pick();
    return () => { observer.disconnect(); root.removeEventListener("scroll", onScroll); };
  }, [scroller, key]);
}

/** Plynulý posun konverzace na kotvu (tah nebo karta otázky). */
export function scrollToAnchor(anchor: string): void {
  const el = document.getElementById(anchor);
  if (!el) return;
  const reduce = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}
