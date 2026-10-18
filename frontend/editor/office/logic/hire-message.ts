// Posadit agenta (docs/kancelar.md §3): předvyplněná zpráva a název relace pro stůl (karta) nebo
// společný stůl místnosti (sektor). Zpráva se jen předvyplní, odešle ji člověk (docs/asistent.md).
import type { StartRequest } from "@/layout/assistant-panel/logic/use-start-request";

export type HireTarget = { kind: "node" | "sector"; id: string; name: string };

export const TITLE_MAX = 60;

const nameOf = (target: HireTarget) => target.name.trim() || (target.kind === "node" ? "Nepojmenovaná karta" : "Nepojmenovaný sektor");

/** Text, kterým se pole zprávy předvyplní (§3.3). */
export function hireDraft(target: HireTarget): string {
  const name = nameOf(target);
  return target.kind === "node"
    ? `Pracuj na kartě «${name}» (\`${target.id}\`). Načti \`node-brief\`, drž se cíle a akceptace, výsledek dej jako \`agent-output\` přes skill opora-control-center.`
    : `Jsi v sektoru «${name}» (\`${target.id}\`). Přečti jeho cíl, akceptaci a bránu; navrhni další krok (rozklad na karty / shrnutí podnětů / kritika), nic nezapisuj bez schválení.`;
}

/** Název relace: název karty, nebo „Sektor: název“; nejvýš 60 znaků (§3.4). */
export function hireTitle(target: HireTarget): string {
  const title = target.kind === "node" ? nameOf(target) : "Sektor: " + nameOf(target);
  return title.length > TITLE_MAX ? title.slice(0, TITLE_MAX).trimEnd() : title;
}

/** Žádost o novou relaci bez pořadového čísla; to přidělí App. */
export function hireRequest(target: HireTarget, workspace: string): Omit<StartRequest, "seq"> {
  return {
    workspace,
    nodeId: target.kind === "node" ? target.id : null,
    sectorId: target.kind === "sector" ? target.id : null,
    title: hireTitle(target),
    draft: hireDraft(target),
  };
}
