// Čipy „Zdroje“ nad mapou z `GET /api/oporahub/process-health` (docs/zivy-proces.md §6). Kancelář je živá,
// když poslala něco za posledních `officeFreshMinutes`; jinak odpojená (s časem poslední události) nebo
// „bez událostí“, když nikdy nic neposlala. Opora a GitHub ukazují stáří poslední události, OpenViking stav
// paměti. Bez odpovědi serveru se nic nedomýšlí: čip říká „neznámo“.
export type Tone = "ok" | "warn" | "bad" | "gap";
export type SourceChip = { id: string; name: string; state: string; age: string; tone: Tone; tip: string };
type SourceAge = { lastAt: string | null; ageSeconds: number | null };
export type ProcessHealth = {
  now: string; officeConnected: boolean; officeFreshMinutes: number; listeners: number;
  sources: { office?: SourceAge; opora?: SourceAge; github?: SourceAge };
  memory?: { status: string; reason?: string } | null;
};

export function age(seconds: number | null | undefined) {
  if (seconds == null) return "bez událostí";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${Math.round(seconds / 3600)} h`;
}

const MEMORY: Record<string, [string, Tone]> = {
  configured: ["připojeno", "ok"], disabled: ["vypnuto", "gap"], unavailable: ["nedostupné", "bad"], needs_provisioning: ["nenastaveno", "warn"],
};

export function sourceChips(health: ProcessHealth | null): SourceChip[] {
  if (!health) return ["Kancelář", "Opora", "GitHub", "OpenViking"].map((name) => ({ id: name, name, state: "neznámo", age: "—", tone: "gap", tip: "Zdraví toku zatím nepřišlo." }));
  const office = health.sources.office, opora = health.sources.opora, github = health.sources.github;
  const plain = (id: string, name: string, item: SourceAge | undefined): SourceChip => item?.lastAt
    ? { id, name, state: "naposledy", age: age(item.ageSeconds), tone: "ok", tip: `poslední událost ${item.lastAt}` }
    : { id, name, state: "bez událostí", age: "—", tone: "gap", tip: "Zdroj v tomto prostoru zatím nic nehlásil." };
  const officeChip: SourceChip = health.officeConnected
    ? { id: "office", name: "Kancelář", state: "živě", age: age(office?.ageSeconds), tone: "ok", tip: `poslední událost ${office?.lastAt ?? "—"}` }
    : office?.lastAt
      ? { id: "office", name: "Kancelář", state: "odpojeno", age: age(office.ageSeconds), tone: "bad", tip: `nic za posledních ${health.officeFreshMinutes} min · poslední ${office.lastAt}` }
      : { id: "office", name: "Kancelář", state: "bez událostí", age: "—", tone: "gap", tip: "Kancelář do tohoto prostoru zatím nic neposlala." };
  const [memoryState, memoryTone] = MEMORY[health.memory?.status ?? ""] ?? ["neznámo", "gap" as Tone];
  return [officeChip, plain("opora", "Opora", opora), plain("github", "GitHub", github),
    { id: "memory", name: "OpenViking", state: memoryState, age: "", tone: memoryTone, tip: health.memory?.reason ?? "" }];
}

/** Úzký parser: čtou se jen pole, která pohled ukazuje; cokoli jiného je chyba čtení. */
export function parseProcessHealth(raw: unknown): ProcessHealth {
  const value = raw as ProcessHealth | null;
  if (!value || typeof value !== "object" || typeof value.officeConnected !== "boolean" || !value.sources || typeof value.sources !== "object")
    throw new Error("Zdraví živého procesu má neplatný tvar.");
  return value;
}
