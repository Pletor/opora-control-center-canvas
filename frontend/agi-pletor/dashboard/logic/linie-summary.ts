import { list, rec, str, type Raw } from "./view-common";

/**
 * Pět os, souhrn, akce a snímek z `GET /board` (docs/navrhy/2026-11-06-linie-rebrand.md §2a, §4). Frontend pravidla
 * §2a nepočítá: čte, co spočítal backend, a když pole chybí (backend před L7a), odvodí jen text ze `stateLabel`/`next`.
 * Výrok Pletora skládá výhradně z `axes` + `summary` + stáří zdrojů; co v nich není, říká jako „nevím“.
 */
export type SummaryKey = "blocked" | "merged" | "todo" | "wip" | "failed" | "nocheck" | "checking" | "stale" | "pending" | "accepted" | "parked" | "unknown";
export type Summary = { key: SummaryKey; text: string; reason: string; next: string; derived: boolean };
export type Axes = {
  work: { state: string; src: string };
  checks: { state: string; sha: string; src: string };
  acceptance: { state: string; sha: string; src: string };
  integration: { state: string; target: string; sha: string; at: string; mode: string; src: string };
  deploy: { envs: Record<string, string>; src: string };
};
export type Evidence = { kind: string; ref: string; at: string; src: string };
/** Vazba na plán (L7d): `issued` = zmrazená revize zadání při vydání práce; `diff` = karta se od vydání změnila. */
export type Plan = { state: string; text: string; diff: boolean; planCardId: string; directionCardId: string; cardRevision: string; issued: { cardId: string; cardRevision: string; at: string } | null };
export type Judgement = { summary: Summary; axes: Axes | null; allowed: string[]; blocked: Record<string, string>; incomplete: string[]; evidence: Evidence[]; plan: Plan | null };
export type Source = { name: string; verifiedAt: string; ok: boolean };
export type Snapshot = { id: string; builtAt: string; sources: Source[] };

export const KEYS: SummaryKey[] = ["blocked", "merged", "todo", "wip", "failed", "nocheck", "checking", "stale", "pending", "accepted", "parked"];
/** Dnešní `state` (před L7a) → klíč souhrnu. Jen náhradní čtení; jakmile backend pošle `summary.key`, platí ten. */
export const LEGACY_KEY: Record<string, SummaryKey> = {
  open: "wip", awaiting_checks: "checking", blocked: "blocked", deferred: "parked", accepted_unmerged: "accepted", merged: "merged", stale: "stale",
};
const stringMap = (value: unknown) => Object.fromEntries(Object.entries(rec(value)).map(([k, v]) => [k, str(v)]).filter(([, v]) => v));

function axesOf(raw: unknown): Axes | null {
  const a = rec(raw);
  if (!Object.keys(a).length) return null;
  const w = rec(a.work), c = rec(a.checks), acc = rec(a.acceptance), i = rec(a.integration), d = rec(a.deploy);
  return {
    work: { state: str(w.state), src: str(w.src) },
    checks: { state: str(c.state), sha: str(c.sha), src: str(c.src) },
    acceptance: { state: str(acc.state), sha: str(acc.sha), src: str(acc.src) },
    integration: { state: str(i.state), target: str(i.target), sha: str(i.sha), at: str(i.at), mode: str(i.mode), src: str(i.src) },
    deploy: { envs: stringMap(d.envs), src: str(d.src) },
  };
}

export function planOf(raw: unknown): Plan | null {
  const p = rec(raw);
  if (!str(p.state)) return null;
  const issued = rec(p.issued);
  return { state: str(p.state), text: str(p.text), diff: p.diff === true, planCardId: str(p.planCardId), directionCardId: str(p.directionCardId), cardRevision: str(p.cardRevision),
    issued: Object.keys(issued).length ? { cardId: str(issued.cardId), cardRevision: str(issued.cardRevision), at: str(issued.at) } : null };
}

/** Kulička z boardu → souhrn, osy a akce. Bez `summary` se text vezme ze `stateLabel` a klíč z `LEGACY_KEY`. */
export function judgementOf(ball: Raw): Judgement {
  const s = rec(ball.summary);
  const has = Object.keys(s).length > 0;
  const key = KEYS.includes(s.key as SummaryKey) ? (s.key as SummaryKey) : LEGACY_KEY[str(ball.state)] ?? "unknown";
  return {
    summary: { key, text: str(s.text) || str(ball.stateLabel), reason: str(s.reason), next: str(s.next) || str(ball.next), derived: !has },
    axes: axesOf(ball.axes),
    allowed: list(ball.allowed).map(str).filter(Boolean),
    blocked: stringMap(ball.blocked),
    incomplete: list(ball.incomplete).map(str).filter(Boolean),
    evidence: list(ball.evidence).map((item) => { const e = rec(item); return { kind: str(e.kind), ref: str(e.ref), at: str(e.at), src: str(e.src) }; }).filter((e) => e.kind),
    plan: planOf(ball.plan),
  };
}

export function snapshotOf(raw: unknown): Snapshot | null {
  const s = rec(raw);
  if (!Object.keys(s).length) return null;
  const sources = Object.entries(rec(s.sources)).map(([name, value]) => ({ name, verifiedAt: str(rec(value).verifiedAt), ok: rec(value).ok !== false }));
  return { id: str(s.id), builtAt: str(s.builtAt), sources };
}

export const STALE_MS = 10 * 60 * 1000;
const SOURCE_LABEL: Record<string, string> = { git: "git", prs: "PR (GitHub)", checks: "kontroly", sessions: "relace", deploy: "nasazení" };

/** „právě teď“, „před 4 min“, „před 2 h“; neznámý čas = „nikdy“. */
export function ago(iso: string, now: number): string {
  const t = Date.parse(iso);
  if (!iso || Number.isNaN(t)) return "nikdy";
  const min = Math.max(0, Math.round((now - t) / 60000));
  return min < 1 ? "právě teď" : min < 120 ? `před ${min} min` : `před ${Math.round(min / 60)} h`;
}
export const hhmm = (iso: string) => { const d = new Date(iso); return !iso || Number.isNaN(d.getTime()) ? "—" : `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };

/** Stáří každého zdroje zvlášť proti `now` (ne proti času načtení stránky): ≥ 10 min nebo `ok:false` = zastaralé. */
export function sourceAges(snapshot: Snapshot | null, now: number): { name: string; text: string; stale: boolean }[] {
  return (snapshot?.sources ?? []).map((source) => {
    const t = Date.parse(source.verifiedAt);
    const stale = !source.ok || Number.isNaN(t) || now - t >= STALE_MS;
    return { name: source.name, text: `${SOURCE_LABEL[source.name] ?? source.name} ${ago(source.verifiedAt, now)}${stale ? " · zastaralé" : ""}`, stale };
  });
}

/**
 * Čerstvost čtení boardu: hodiny tikají samy (ne až po úspěchu), takže při výpadku API stáří dál roste a panel to řekne.
 */
export function feedText(lastSuccessAt: number | null, lastError: string, now: number): string {
  if (!lastError) return "";
  const since = lastSuccessAt === null ? "zatím žádné úspěšné čtení" : `poslední úspěšné čtení ${ago(new Date(lastSuccessAt).toISOString(), now)}`;
  return `${since} · nyní nedostupné`;
}

const sha7 = (sha: string) => sha.slice(0, 7);
const sourceAge = (snapshot: Snapshot | null, name: string, now: number) => {
  const source = snapshot?.sources.find((item) => item.name === name);
  return source ? ago(source.verifiedAt, now) : "";
};

// OP-159D4C.1: výrok Pletora je jen převyprávění os a souhrnu; co osa nedokazuje, se říká jako „nemám“ / „neznám“.
export function pletorVerdict(name: string, j: Judgement, snapshot: Snapshot | null, now: number): string[] {
  const head = `${name} ${j.summary.text || "bez souhrnu"}.`;
  const a = j.axes;
  if (!a) return [head, "Osy s důkazy backend zatím neposlal; řídím se jen textem stavu."];
  const where = (src: string, source: string) => [src, sourceAge(snapshot, source, now)].filter(Boolean).join(", ");
  const c = a.checks, rev = c.sha ? `revize ${sha7(c.sha)}` : "této revize";
  const checks = c.state === "passed" ? `Kontroly ${rev} prošly (${where(c.src, "checks")}).`
    : c.state === "failed" ? `Kontroly ${rev} selhaly (${where(c.src, "checks")}).`
      : c.state === "running" ? `Kontroly ${rev} běží (${where(c.src, "checks")}).`
        : c.state === "missing" ? "Kontroly pro aktuální revizi chybí." : "Stav kontrol neznám.";
  const acc = a.acceptance;
  const accept = acc.state === "accepted" ? `Přijato pro ${sha7(acc.sha)}.` : acc.state === "stale" ? `Přijetí platilo pro ${sha7(acc.sha)}, HEAD je jiný.` : "";
  const merged = a.integration.state === "merged";
  const envs = Object.entries(a.deploy.envs);
  const flow = merged && envs.length ? `Začleněno do ${a.integration.target} (${sha7(a.integration.sha)}${a.integration.mode ? `, ${a.integration.mode}` : ""}).`
    : merged ? `Začleněno do ${a.integration.target} (${sha7(a.integration.sha)}${a.integration.mode ? `, ${a.integration.mode}` : ", způsob neověřen"}). Nasazení potvrzené nemám.`
      : envs.length ? "Začlenění potvrzené nemám." : "Začlenění ani nasazení potvrzené nemám.";
  const deploy = envs.length ? `Běží: ${envs.map(([env, sha]) => `${env}@${sha7(sha)}`).join(", ")}.` : "";
  const prs = j.incomplete.includes("prs") ? `Stav PR neznám (GitHub ${sourceAge(snapshot, "prs", now) || "bez záznamu"}).` : "";
  return [head, checks, accept, flow, deploy, prs].filter(Boolean);
}
