// Posadit agenta (docs/kancelar.md §3): připravený text pro srdce ke stolu (karta) nebo ke společnému
// stolu místnosti (sektor). Text jde srdci zprávou; pracovníka posadí srdce úkolem přes bránu.
import type { HeartRequest } from "@/layout/heart-channel/logic/heart-api";

export type HireTarget = { kind: "node" | "sector"; id: string; name: string };

const nameOf = (target: HireTarget) => target.name.trim() || (target.kind === "node" ? "Nepojmenovaná karta" : "Nepojmenovaný sektor");

/** Text zprávy srdci (§3.3). */
export function hireText(target: HireTarget): string {
  const name = nameOf(target);
  return target.kind === "node"
    ? `Posaď pracovníka ke kartě «${name}» (\`${target.id}\`): zadej úkol podle jejího \`node-brief\` (cíl a akceptace).`
    : `Projdi sektor «${name}» (\`${target.id}\`): přečti jeho cíl, akceptaci a bránu a navrhni další krok (rozklad na karty / shrnutí podnětů / kritika).`;
}

/** Žádost pro App: prostor, kterého se týká, a text zprávy srdci. */
export function hireRequest(target: HireTarget, workspace: string): HeartRequest {
  return { workspace, text: hireText(target) };
}
