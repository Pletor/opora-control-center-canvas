// Inspektor vybrané karty: kdo je na tahu, odkazy (běh, větev, PR, commit, patro), kontroly a časová osa.
// Všechno je z řádku mapy (snímek karty + její události); co zdroj neposlal, zůstane „—“.
import type { Lane } from "../../logic/lanes";
import type { FlowEvent } from "../../logic/process-event";

export type Turn = { label: string; who: string; what: string; human: boolean };
export type InspectorRefs = { run: string; branch: string; pr: string; prUrl: string; sha: string; floor: string };
export type CheckRow = { key: string; state: FlowEvent["state"]; name: string; result: string };

const first = (events: FlowEvent[], pick: (event: FlowEvent) => string | number | null) => {
  for (const event of events) { const value = pick(event); if (value) return String(value); }
  return "";
};

/** Kdo je na tahu: člověk, když poslední událost čeká na něj; jinak držitel lease nebo pracovník. */
export function turnOf(lane: Lane): Turn {
  const what = lane.last?.title ?? lane.card?.reason ?? "";
  if (lane.blocker?.human) return { label: "Čeká na člověka", who: "Vy", what, human: true };
  const who = lane.card?.lease?.holder || lane.workerName;
  if (who) return { label: "Na tahu", who, what, human: false };
  return { label: "Na tahu", who: "nikdo", what: what || "Karta nemá aktivní běh.", human: false };
}

/** Odkazy z nejnovější události, která pole nese; PR je odkaz jen s adresou https od zdroje. */
export function refsOf(lane: Lane): InspectorRefs {
  const events = lane.events;
  const url = first(events, (event) => /^https:\/\//.test(event.url) && /\/pull\//.test(event.url) ? event.url : "");
  return {
    run: lane.card?.executionId || first(events, (event) => event.executionId) || "—",
    branch: first(events, (event) => event.branch) || "—",
    pr: (() => { const pr = first(events, (event) => event.pr); return pr ? `#${pr}` : ""; })(),
    prUrl: url, sha: first(events, (event) => event.sha).slice(0, 12) || "—", floor: first(events, (event) => event.floor) || "—",
  };
}

/** Kontroly = události fáze Kontroly; pro každou kontrolu (cíl nástroje, jinak druh) jen nejnovější. */
export function checksOf(lane: Lane, limit = 6): CheckRow[] {
  const rows = new Map<string, CheckRow>();
  for (const event of lane.events) {
    if (event.phase !== 3) continue;
    const name = event.tool?.target || event.tool?.name || event.kind;
    if (!rows.has(name)) rows.set(name, { key: event.key, state: event.state, name, result: event.title });
  }
  return [...rows.values()].slice(0, limit);
}
