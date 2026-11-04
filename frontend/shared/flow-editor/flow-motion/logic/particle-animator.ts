// Jediný běh pohybu plátna Studia (způsob z prototypu `animations.mjs`, `FlowAnimator`): jeden `requestAnimationFrame`
// pro všechny tečky, poloha z `path.getPointAtLength` a přímý zápis `cx`/`cy` do SVG, žádný stav Reactu na snímek.
// Čas drží `PresentationClock`: skrytý dokument a omezený pohyb nepřičítají čas a po návratu se nic nedohání. Bez teček
// smyčka stojí. Prostředí (čas, snímek, viditelnost, preference) je vstříknuté, aby šlo animátor testovat bez prohlížeče.
import { PresentationClock } from "./presentation-clock";
import { loopProgress, onceProgress } from "./progress";

export type MotionPath = { getTotalLength(): number; getPointAtLength(distance: number): { x: number; y: number } };
export type MotionDot = { setAttribute(name: string, value: string): void };
export type ParticleSpec =
  | { dot: MotionDot; path: MotionPath; mode: "loop"; cycle: number; index: number; dots: number }
  | { dot: MotionDot; path: MotionPath; mode: "once"; delay: number; duration: number };
type Particle = ParticleSpec & { length: number; start: number };

export type MotionEnv = {
  now(): number;
  frame(callback: (time: number) => void): number;
  cancel(id: number): void;
  hidden(): boolean;
  reduced(): boolean;
  /** Přihlásí posluchače změny viditelnosti a preference pohybu; vrací odhlášení. */
  watch(onChange: () => void): () => void;
};

export class ParticleAnimator {
  readonly clock = new PresentationClock();
  private particles = new Set<Particle>();
  private frameId = 0;
  private unwatch: (() => void) | null = null;

  constructor(private env: MotionEnv) {
    this.clock.setFrame({ running: true, key: "studio" }, env.now());
  }

  /** Napojí se na viditelnost a preferenci pohybu (volá plátno po připojení). */
  attach(): void {
    this.unwatch ??= this.env.watch(() => { this.clock.resync(this.env.now()); this.ensureLoop(); });
  }

  detach(): void {
    this.unwatch?.(); this.unwatch = null;
    this.env.cancel(this.frameId); this.frameId = 0;
  }

  /** Přidá tečku; jednorázová začíná teď. Vrací odebrání. */
  add(spec: ParticleSpec): () => void {
    if (!this.frameId) this.clock.resync(this.env.now());
    const particle: Particle = { ...spec, length: spec.path.getTotalLength(), start: this.clock.time };
    this.particles.add(particle);
    this.place(particle);
    this.ensureLoop();
    return () => { this.particles.delete(particle); };
  }

  get size(): number { return this.particles.size; }
  get looping(): boolean { return this.frameId !== 0; }

  private ensureLoop(): void {
    if (this.frameId || !this.particles.size || this.env.reduced() || this.env.hidden()) return;
    this.frameId = this.env.frame(this.step);
  }

  private step = (time: number): void => {
    this.frameId = 0;
    const suspended = this.env.hidden() || this.env.reduced();
    this.clock.advance(time, suspended);
    for (const particle of this.particles) this.place(particle);
    if (!suspended) this.ensureLoop();
  };

  private place(particle: Particle): void {
    const progress = particle.mode === "loop"
      ? loopProgress(this.clock.time, particle.cycle, particle.index, particle.dots)
      : onceProgress(this.clock.time, particle.start, particle.delay, particle.duration);
    if (progress === null) { particle.dot.setAttribute("visibility", "hidden"); return; }
    const point = particle.path.getPointAtLength(progress * particle.length);
    particle.dot.setAttribute("cx", point.x.toFixed(2));
    particle.dot.setAttribute("cy", point.y.toFixed(2));
    particle.dot.setAttribute("visibility", "visible");
  }
}

/** Prostředí prohlížeče: `performance.now`, `requestAnimationFrame`, `document.hidden`, `prefers-reduced-motion`. */
export function browserMotionEnv(): MotionEnv {
  const query = typeof matchMedia === "function" ? matchMedia("(prefers-reduced-motion: reduce)") : null;
  return {
    now: () => performance.now(),
    frame: (callback) => requestAnimationFrame(callback),
    cancel: (id) => cancelAnimationFrame(id),
    hidden: () => document.hidden,
    reduced: () => !!query?.matches,
    watch: (onChange) => {
      document.addEventListener("visibilitychange", onChange);
      query?.addEventListener("change", onChange);
      return () => { document.removeEventListener("visibilitychange", onChange); query?.removeEventListener("change", onChange); };
    },
  };
}
