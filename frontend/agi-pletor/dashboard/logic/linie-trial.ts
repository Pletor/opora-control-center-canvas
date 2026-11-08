import { list, rec, str } from "./view-common";

/**
 * Zkouška v živém náhledu (docs/navrhy/2026-11-08-linie-zkouska.md §3–§8): `trial` u kuličky, ticketu i řádku fronty.
 * Backend počítá stav i novinky; prohlížeč jen skládá větu a vybírá, co dělá tlačítko Vyzkoušet. Chybějící `trial`
 * (starý backend) = `none`: náhled neběží, nevyzkoušeno.
 */
export type TrialState = "none" | "building" | "current" | "stale" | "failed";
export type Trial = {
  state: TrialState; url: string; sha: string; head: string; tried: { sha: string; at: string } | null; triedCurrent: boolean;
  news: { sha: string; subject: string }[]; newsMore: number;
  /** Jak vyzkoušet: kroky z `tryout.steps` (report agenta); starý backend = []. */
  steps: string[];
};
/** Co udělá Vyzkoušet: `start` spustí náhled, `open` otevře URL (a zapíše zkoušku), `wait` = staví se. */
export type TrialButton = { kind: "start" | "open" | "wait"; label: string; enabled: boolean; why: string; note: string };

const STATES: TrialState[] = ["none", "building", "current", "stale", "failed"];
const short = (sha: string) => sha.slice(0, 7);

export function trialOf(raw: unknown): Trial {
  const t = rec(raw), tried = rec(t.tried);
  const state = STATES.find((s) => s === t.state) ?? "none";
  return {
    state, url: str(t.url), sha: str(t.sha), head: str(t.head), tried: str(tried.sha) ? { sha: str(tried.sha), at: str(tried.at) } : null,
    triedCurrent: t.triedCurrent === true,
    news: list(t.news).map((item) => ({ sha: str(rec(item).sha), subject: str(rec(item).subject) })).filter((n) => n.sha),
    newsMore: typeof t.newsMore === "number" && t.newsMore > 0 ? t.newsMore : 0,
    steps: list(t.steps).filter((s): s is string => typeof s === "string" && s.trim() !== ""),
  };
}

/** Stav náhledu jednou větou. */
export function trialSentence(t: Trial): string {
  switch (t.state) {
    case "current": return `běží na ${short(t.sha)} · aktuální`;
    case "building": return `staví se na ${short(t.sha || t.head)}`;
    case "stale": return `zastaralý, hlava je ${short(t.head)}`;
    case "failed": return "selhal";
    default: return "náhled neběží";
  }
}

/** Evidence zkoušky: na čem člověk naposledy zkoušel, a jestli to je hlava. */
export function triedSentence(t: Trial): string {
  if (!t.tried) return "nevyzkoušeno";
  const on = `vyzkoušeno na ${short(t.tried.sha)}`;
  return t.triedCurrent || !t.head ? on : `${on}, hlava je ${short(t.head)}`;
}

/** Tlačítko Vyzkoušet; spuštění náhledu smí jen tehdy, když ho pravidlo povoluje (`start` = akce `preview` z allowed). */
export function trialButton(t: Trial, start?: { enabled: boolean; why: string }): TrialButton {
  if (t.state === "building") return { kind: "wait", label: "staví se…", enabled: false, why: "náhled se staví", note: "" };
  if ((t.state === "current" || t.state === "stale") && t.url) {
    return { kind: "open", label: "Vyzkoušet", enabled: true, why: "", note: t.state === "stale" ? "zastaralý, přestaví se sám po reportu" : "" };
  }
  const enabled = start ? start.enabled : true;
  return { kind: "start", label: "Vyzkoušet", enabled, why: enabled ? "" : start?.why || "náhled teď spustit nejde", note: "" };
}

/** Commity od poslední zkoušky (sha7 a předmět), za nimi „+N“, když jich backend ořízl víc. */
export function newsLines(t: Trial): string[] {
  return [...t.news.map((n) => `${short(n.sha)} ${n.subject}`), ...(t.newsMore ? [`+${t.newsMore}`] : [])];
}

export const newsCount = (t: Trial) => t.news.length + t.newsMore;

/** Přijetí jen vyzkoušené hlavy: dokud zkouška neplatí pro hlavu, primární akce je Vyzkoušet. */
export const primaryChoice = (t: Trial): "try" | "accept" => (t.triedCurrent ? "accept" : "try");
