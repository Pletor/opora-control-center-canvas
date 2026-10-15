// Spustitelná buňka Schránky jen pro čtení (docs/schranka-bunka.md §3, §5): kontroly plánu u brány Syntetizováno
// a nahlášený běh kontrol u brány Ověřeno. Běh je přiřazený, ne atestovaný, proto se nikdy netvrdí „ověřeno“. Bez Reactu.

const MAX_CHECKS = 4;

export type CheckLine = { id: string; command: string; text: string };

/** Řádky „kontroly: <id> `<command>`“ ze `synthesized.payload.checks` (max 4; neplatné položky se přeskočí). */
export function checkLines(payload: unknown): CheckLine[] {
  const checks = payload && typeof payload === "object" ? (payload as Record<string, unknown>).checks : undefined;
  if (!Array.isArray(checks)) return [];
  const lines: CheckLine[] = [];
  for (const item of checks) {
    if (!item || typeof item !== "object") continue;
    const { id, command } = item as Record<string, unknown>;
    if (typeof id !== "string" || typeof command !== "string") continue;
    lines.push({ id, command, text: `kontroly: ${id} \`${command}\`` });
    if (lines.length === MAX_CHECKS) break;
  }
  return lines;
}

export type RunCheckView = { checkId: string; passed: boolean; text: string };
export type RunView = { badge: string; who: string; checks: RunCheckView[] };

/** Nahlášený běh z `verified.payload` (`actual.run`, `runTrust`). `null`, když běh chybí.
 *  Štítek je „běh nahlášen – neatestováno“ při `runTrust: "reported"` i bez `runTrust`; jiná hodnota se jen opíše. */
export function runView(payload: unknown): RunView | null {
  if (!payload || typeof payload !== "object") return null;
  const p = payload as Record<string, unknown>;
  const actual = p.actual && typeof p.actual === "object" ? (p.actual as Record<string, unknown>) : null;
  const run = actual?.run;
  if (!run || typeof run !== "object") return null;
  const r = run as Record<string, unknown>;
  const trust = p.runTrust;
  const badge = trust === undefined || trust === "reported" ? "běh nahlášen – neatestováno" : `běh: ${String(trust)} – neatestováno`;
  const executor = typeof r.executor === "string" && r.executor ? r.executor : "neznámý";
  const verifier = typeof r.verifier === "string" && r.verifier ? r.verifier : "neznámý";
  const checks = (Array.isArray(r.checks) ? r.checks : []).flatMap((item): RunCheckView[] => {
    if (!item || typeof item !== "object") return [];
    const c = item as Record<string, unknown>;
    if (typeof c.checkId !== "string" || typeof c.exitCode !== "number") return [];
    const ms = typeof c.durationMs === "number" ? c.durationMs : 0;
    const passed = c.exitCode === 0;
    return [{ checkId: c.checkId, passed, text: `${c.checkId} · exit ${c.exitCode} (${passed ? "prošla" : "neprošla"}) · ${ms} ms` }];
  });
  return { badge, who: `vykonal ${executor} · ověřil ${verifier}`, checks };
}
