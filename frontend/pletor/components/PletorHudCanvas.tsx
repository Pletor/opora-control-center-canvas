import { useEffect, useRef } from "react";
import { drawHud, stepHud, type HudFrame } from "../logic/hud-draw";
import { hudPalette, type HudState } from "../logic/hud-palette";

/**
 * Plátno kokpitu: jedna rAF smyčka kreslí prstence a jádro podle stavu od rodiče.
 * Ve skryté záložce smyčka stojí; po odmontování (režim není HUD) se uklidí smyčka i pozorovatel.
 * FPS hlásí rodiči jednou za půl sekundy, ne každým snímkem. `level` (P3) čte každým snímkem hlasitost hlasu.
 * V malém ho skládá i popup Poslechu (vlastní `className`, bez FPS).
 */
export default function PletorHudCanvas({ state, level, onFps = () => undefined, className = "pletor-hud__canvas" }: {
  state: HudState; level: () => number | null; onFps?: (fps: number) => void; className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(state);
  const fpsRef = useRef(onFps);
  const levelRef = useRef(level);
  stateRef.current = state;
  fpsRef.current = onFps;
  levelRef.current = level;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const font = getComputedStyle(canvas).getPropertyValue("--mono").trim() || "monospace";
    const frame: HudFrame = { w: 0, h: 0, t: 0, rot: 0, amp: 0, font };
    let raf = 0;
    let last = 0;
    let fpsFrames = 0;
    let fpsSince = 0;

    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const box = canvas.getBoundingClientRect();
      frame.w = Math.max(1, Math.floor(box.width));
      frame.h = Math.max(1, Math.floor(box.height));
      canvas.width = frame.w * dpr;
      canvas.height = frame.h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const tick = (now: number) => {
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
      last = now;
      frame.t = now / 1000;
      stepHud(frame, dt, stateRef.current, reduced, levelRef.current());
      drawHud(ctx, frame, hudPalette(stateRef.current), stateRef.current);
      fpsFrames++;
      if (now - fpsSince > 500) {
        if (fpsSince) fpsRef.current(Math.round((fpsFrames * 1000) / (now - fpsSince)));
        fpsFrames = 0;
        fpsSince = now;
      }
      raf = requestAnimationFrame(tick);
    };
    const start = () => { if (!raf && !document.hidden) { last = 0; raf = requestAnimationFrame(tick); } };
    const stop = () => { cancelAnimationFrame(raf); raf = 0; };
    const visibility = () => (document.hidden ? stop() : start());

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    document.addEventListener("visibilitychange", visibility);
    start();
    return () => {
      stop();
      observer.disconnect();
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
