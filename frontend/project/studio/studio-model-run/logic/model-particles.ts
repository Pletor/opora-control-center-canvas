// Částice MODELu po vazbách (prototyp `animations.mjs`, `FlowAnimator`): pro každý druh toku vazby (přijato,
// odmítnuto, chybová odpověď) 1–5 částic podle množství (log₂), perioda `clamp(1400 + latence·12, 800, 6000)` ms.
// Přijatá částice synchronní vazby s odpovědí jede tam, chvíli setrvá (podle latence) a vrací se ztlumená; odmítnutá
// dojede do 55 % a odrazí se zpět; chybová odpověď jede jen zpět. Barva přijatých podle typu portu, chyby a odmítnutí
// růžově. Milisekundy popisují prezentaci, ne měření. Čistá logika bez DOM.
import { portColor } from "../../model/logic/catalog";
import type { PortType } from "../../model/logic/model-types";
import type { LinkFlow } from "./run-view";

export const MAX_PARTICLES_PER_KIND = 5;
export const ERROR_COLOR = "#ff7397";
export type ParticleKind = "accepted" | "rejected" | "error-response";
export type FlowParticle = { kind: ParticleKind; ordinal: number; count: number; duration: number; roundTrip: boolean; dwell: number; amount: number; color: string };

export const particleDuration = (latencyMs: number) => Math.max(800, Math.min(6000, 1400 + (latencyMs || 0) * 12));
export const particleCount = (amount: number) => Math.min(MAX_PARTICLES_PER_KIND, Math.max(1, Math.ceil(Math.log2(amount + 1) / 3)));

/** Částice jedné vazby podle vypočteného toku; nulový druh nemá žádnou. */
export function linkParticles(flow: LinkFlow): FlowParticle[] {
  const duration = particleDuration(flow.latencyMs), dwell = Math.min(.35, .05 + (flow.latencyMs || 0) / 300);
  const amounts: [ParticleKind, number][] = [["accepted", flow.accepted], ["rejected", flow.rejected], ["error-response", flow.errorResponse]];
  const answered = Math.min(1, flow.response / Math.max(1, flow.accepted));
  return amounts.flatMap(([kind, amount]) => {
    if (!(amount > 0)) return [];
    const count = particleCount(amount), returning = kind === "accepted" ? Math.round(count * answered) : 0;
    return Array.from({ length: count }, (_, ordinal) => ({
      kind, ordinal, count, duration, dwell, amount, roundTrip: ordinal < returning,
      color: kind === "accepted" ? portColor(flow.type as PortType) : ERROR_COLOR,
    }));
  });
}

/** Poloha částice na trase (0–1) a zda jede zpět. Omezený pohyb: pevná místa rovnoměrně po trase. */
export function particleProgress(particle: FlowParticle, time: number, reduced = false): { progress: number; returning: boolean } {
  const f = reduced ? (particle.ordinal + 1) / (particle.count + 1) : ((time % particle.duration) / particle.duration + particle.ordinal / particle.count) % 1;
  if (particle.kind === "rejected") return f < .55 ? { progress: f / .55, returning: false } : { progress: 1 - (f - .55) / .45, returning: true };
  if (particle.kind === "error-response") return { progress: 1 - f, returning: true };
  if (!particle.roundTrip) return { progress: f, returning: false };
  const travel = (1 - particle.dwell) / 2;
  if (f < travel) return { progress: f / travel, returning: false };
  if (f < travel + particle.dwell) return { progress: 1, returning: false };
  return { progress: 1 - (f - travel - particle.dwell) / travel, returning: true };
}
