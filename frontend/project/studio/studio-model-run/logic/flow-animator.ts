// Animátor částic MODELu (prototyp `animations.mjs`, `FlowAnimator`): jeden `requestAnimationFrame` pro celé plátno,
// poloha z `path.getPointAtLength`, přímý zápis `cx`/`cy`, žádný stav Reactu na snímek. Na rozdíl od animátoru
// Skutečnosti (`studio-motion`, stále běžící hodiny) jde čas jen za běhu: snímek běhu (`setFrame`) předá hodinám
// `PresentationClock` běží/stojí a tick, takže Pause plátno zmrazí a Step posune fázi o 280 ms. Skrytý dokument a
// omezený pohyb čas nepřičítají a smyčku zastaví. Prostředí je vstříknuté (`MotionEnv` ze `studio-motion`).
import { PresentationClock } from "@/shared/flow-editor/flow-motion/logic/presentation-clock";
import type { MotionDot, MotionEnv, MotionPath } from "@/shared/flow-editor/flow-motion/logic/particle-animator";
import { particleProgress, type FlowParticle } from "./model-particles";

export type RunFrame = { running: boolean; tick: number; key: string };
type Placed = { dot: MotionDot; path: MotionPath; length: number; particle: FlowParticle };

export class FlowAnimator {
  readonly clock = new PresentationClock();
  private placed = new Set<Placed>();
  private frameId = 0;
  private unwatch: (() => void) | null = null;

  constructor(private env: MotionEnv) {}

  attach(): void {
    this.unwatch ??= this.env.watch(() => { this.clock.resync(this.env.now()); this.drawAll(); this.ensureLoop(); });
  }

  detach(): void {
    this.unwatch?.(); this.unwatch = null;
    this.env.cancel(this.frameId); this.frameId = 0;
  }

  /** Nový snímek běhu: hodiny zastaví, rozběhnou nebo posunou o krok; částice se hned překreslí. */
  setFrame(frame: RunFrame): void {
    this.clock.setFrame({ ...frame, suspended: this.suspended() }, this.env.now());
    this.drawAll();
    this.ensureLoop();
  }

  /** Přihlásí částici; vrací odhlášení. */
  add(dot: MotionDot, path: MotionPath, particle: FlowParticle): () => void {
    const placed: Placed = { dot, path, length: path.getTotalLength(), particle };
    this.placed.add(placed);
    this.draw(placed);
    this.ensureLoop();
    return () => { this.placed.delete(placed); };
  }

  get size(): number { return this.placed.size; }
  get looping(): boolean { return this.frameId !== 0; }

  private suspended(): boolean { return this.env.hidden() || this.env.reduced(); }

  private ensureLoop(): void {
    if (this.frameId || !this.placed.size || !this.clock.running || this.suspended()) return;
    this.frameId = this.env.frame(this.step);
  }

  private step = (time: number): void => {
    this.frameId = 0;
    this.clock.advance(time, this.suspended());
    this.drawAll();
    this.ensureLoop();
  };

  private drawAll(): void { for (const placed of this.placed) this.draw(placed); }

  private draw({ dot, path, length, particle }: Placed): void {
    const { progress, returning } = particleProgress(particle, this.clock.time, this.env.reduced());
    const point = path.getPointAtLength(Math.max(0, Math.min(1, progress)) * length);
    dot.setAttribute("cx", point.x.toFixed(2));
    dot.setAttribute("cy", point.y.toFixed(2));
    dot.setAttribute("data-direction", returning ? "return" : "forward");
  }
}
