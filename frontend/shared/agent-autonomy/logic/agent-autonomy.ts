// Plná autonomie agentů bez Reactu (docs/plna-autonomie-agenta.md): tvar `agentAutonomy` z nastavení projektu,
// bezpečné čtení odpovědi (chybějící nebo cizí tvar = vypnuto), cesty API a lidská věta pro štítek.

/** Stav přepínače, jak ho vrací `GET /api/project-settings` v poli `agentAutonomy`. */
export type AgentAutonomy = { full: boolean; since?: string; by?: string };

export const AUTONOMY_OFF: AgentAutonomy = { full: false };

/** Zápis přepínače; smí ho jen člověk v UI (relační doklad řeší `api`). */
export const AUTONOMY_WRITE_URL = "/api/project-settings/agent-autonomy";

/** Čtení nastavení projektu, ze kterého se bere `agentAutonomy`. */
export function autonomyReadUrl(project: string): string {
  return "/api/project-settings?" + new URLSearchParams({ project });
}

/** Tělo zápisu přepínače. */
export function autonomyWriteBody(project: string, full: boolean): { project: string; full: boolean } {
  return { project, full };
}

/**
 * Vytáhne `agentAutonomy` z odpovědi nastavení. Cokoli jiného než `full === true` je vypnuto, aby starý
 * server bez pole nebo poškozená odpověď nikdy neukázaly štítek omylem.
 */
export function readAutonomy(response: unknown): AgentAutonomy {
  const raw = response && typeof response === "object" ? (response as { agentAutonomy?: unknown }).agentAutonomy : undefined;
  if (!raw || typeof raw !== "object") return AUTONOMY_OFF;
  const value = raw as Record<string, unknown>;
  const result: AgentAutonomy = { full: value.full === true };
  if (typeof value.since === "string" && value.since) result.since = value.since;
  if (typeof value.by === "string" && value.by) result.by = value.by;
  return result;
}

/** Datum a čas zapnutí česky („28. 10. 2026 14:05“); neplatný čas = prázdný řetězec. */
export function sinceLabel(since: string | undefined): string {
  if (!since) return "";
  const date = new Date(since);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getDate()}. ${date.getMonth() + 1}. ${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Tooltip štítku: co autonomie znamená, od kdy a kdo ji zapnul. */
export function autonomyTitle(autonomy: AgentAutonomy): string {
  const parts = ["Agent smí v projektu všechno co člověk kromě přístupu, připojení repozitáře/složky a klíčů."];
  const since = sinceLabel(autonomy.since);
  if (since) parts.push(`Zapnuto ${since}` + (autonomy.by ? ` (${autonomy.by})` : "") + ".");
  else if (autonomy.by) parts.push(`Zapnul(a) ${autonomy.by}.`);
  return parts.join(" ");
}

/** Brána mozku projektu (`GET /api/brain/gate-setting`): zapnutá a zda ji plná autonomie agentů projde. */
export type BrainGate = { on: boolean; passes: boolean };

export const GATE_OFF: BrainGate = { on: false, passes: false };

export const GATE_URL = "/api/brain/gate-setting";

export function gateReadUrl(project: string): string {
  return GATE_URL + "?" + new URLSearchParams({ project });
}

/** Cokoli jiného než `true` je vypnuto (starý server bez pole `autonomyPassesGate` = brána agenta nepustí). */
export function readGate(response: unknown): BrainGate {
  const value = response && typeof response === "object" ? (response as Record<string, unknown>) : {};
  return { on: value.enabled === true, passes: value.autonomyPassesGate === true };
}

/** Zápis mění jen průchod autonomie; zapnutí brány posílá beze změny, aby ji přepínač omylem nevypnul. */
export function gateWriteBody(project: string, gate: BrainGate, passes: boolean) {
  return { project, enabled: gate.on, autonomyPassesGate: passes };
}
