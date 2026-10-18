// Brány cyklu fragmentu pro oko (docs/schranka-neurony.md §3, §6): osm bran v pevném pořadí, český titulek
// a stav tečky v pruhu stromu. Pravidla bran hlídá server; tady se jen čte, co poslal (`gates`, `gateStep`,
// `gatesStale`, `deadEnd`). Bez Reactu.
import type { GateName, GateSummary } from "./brief-vault-model";

export const GATES: GateName[] = ["scoped", "weighed", "synthesized", "decided", "planned", "placed", "verified", "learned"];

/** Titulek a krátké vysvětlení brány česky (pořadí jako `GATES`). */
export const GATE_TITLES: Record<GateName, { title: string; hint: string }> = {
  scoped: { title: "Vymezeno", hint: "Fragment patří projektu a své disciplíně." },
  weighed: { title: "Zváženo", hint: "Zapsaný přínos a riziko." },
  synthesized: { title: "Mikrokrok", hint: "Typovaný mikrokrok s kritériem hotovo a předpovědí." },
  decided: { title: "Rozhodnuto", hint: "Rozhodnutí ano / jinak / ne s důvodem." },
  planned: { title: "Naplánováno", hint: "Server složil návrh struktury na plátně (dryRun)." },
  placed: { title: "Vloženo", hint: "Karty založené na plátně (schvaluje člověk)." },
  verified: { title: "Ověřeno", hint: "Výsledek porovnaný s předpovědí (predikční chyba)." },
  learned: { title: "Poučení", hint: "Poučení zapsané do paměti disciplíny." },
};

export const gateTitle = (gate: GateName): string => `${GATES.indexOf(gate) + 1}. ${GATE_TITLES[gate].title}`;

/** Tečka pruhu: zapnutá, další na řadě, vypnutá, nebo vypnutá kvůli zneplatnění (jiný otisk vstupů). */
export type GateDotState = "on" | "next" | "off" | "stale";
export type GateDot = { gate: GateName; state: GateDotState; label: string };

/**
 * Osm teček pruhu. Zapnuté jsou platně zapnuté brány; „další na řadě“ je první vypnutá, pokud fragment není
 * slepá ulička; při `gatesStale` se vypnuté tečky kreslí jako zneplatněné (strom neříká, které přesně).
 */
export function gateDots(node: GateSummary): GateDot[] {
  const step = node.gateStep ?? GATES.filter((gate) => node.gates?.[gate]).length;
  return GATES.map((gate, index) => {
    const on = !!node.gates?.[gate];
    const state: GateDotState = on ? "on" : index === step && !node.deadEnd ? "next" : node.gatesStale ? "stale" : "off";
    const word = { on: "zapnutá", next: "další na řadě", off: "vypnutá", stale: "vypnutá, zneplatněná změnou vstupů" }[state];
    return { gate, state, label: `${gateTitle(gate)}: ${word}` };
  });
}

/** Popisek pruhu pro čtečku a titulek řádku: „3/8 bran · další: 4. Rozhodnuto“. */
export function gateBarLabel(node: GateSummary): string {
  const step = node.gateStep ?? 0;
  const round = roundLabel(node);
  if (node.deadEnd) return `${step}/8 bran · slepá ulička (rozhodnuto: ne)`;
  const next = GATES[step];
  return `${step}/8 bran` + (round ? ` · ${round.text}` : "") + (next ? ` · další: ${gateTitle(next)}` : " · cyklus uzavřen") + (node.gatesStale ? " · něco zneplatněno" : "");
}

/** Predikční chyba 0–1 jako text („0,33“), `null` = neověřeno. */
export function formatError(value: number | null | undefined): string {
  return value == null ? "—" : value.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Nejvyšší počet kol cyklu (zrcadlí `MAX_ROUNDS` backendu, §11). */
export const MAX_ROUNDS = 3;

/** Štítek kola fragmentu: „kolo 2/3“, po vyčerpání „vyčerpáno – čeká na člověka“; `null` = server kolo neposlal. */
export function roundLabel(node: { round?: number; exhausted?: boolean }): { text: string; exhausted: boolean } | null {
  if (node.exhausted) return { text: "vyčerpáno – čeká na člověka", exhausted: true };
  if (typeof node.round !== "number") return null;
  return { text: `kolo ${Math.min(node.round, MAX_ROUNDS)}/${MAX_ROUNDS}`, exhausted: false };
}

const LAYERS: Record<string, string> = { frontend: "frontend", backend: "backend", database: "databáze" };

/** Kroky mikrokroku (pole krátkých vět) a štítek vrstvy z payloadu brány `synthesized`; nic neznámého nevrací. */
export function synthesizedView(payload: Record<string, unknown> | null | undefined): { steps: string[]; layer: string | null } {
  const steps = Array.isArray(payload?.steps) ? payload.steps.filter((step): step is string => typeof step === "string" && step !== "") : [];
  const layer = typeof payload?.layer === "string" ? LAYERS[payload.layer] ?? null : null;
  return { steps, layer };
}
