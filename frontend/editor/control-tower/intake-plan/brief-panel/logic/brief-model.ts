// Výslech srdce u požadavku (docs/navrhy/2026-10-30-vyslech-srdce.md §3, §7, řez 3): `brief` z `GET /api/intake`
// → model panelu. Čistá funkce bez Reactu: stav česky, syntéza čitelně (cíl, části s původem, kritéria, hranice),
// otevřené otázky s doporučením, zodpovězené otázky a co do jasna chybí, bez technických klíčů a ID v textu.

export type BriefStatus = "draft" | "research" | "grilling" | "clear";
export type BriefTone = "work" | "ask" | "clear";
export type BriefOrigin = "human" | "research" | "derived" | "other";
export type BriefPart = { text: string; origin: BriefOrigin; originText: string; source: string | null };
export type BriefCriterion = { text: string; checkText: string | null };
export type BriefSynthesis = { goal: string | null; users: string | null; parts: BriefPart[]; acceptance: BriefCriterion[];
  outOfScope: string[] };
export type BriefOpenQuestion = { id: string; text: string; recommended: string; why: string };
export type BriefAnswered = { id: string; text: string; answer: string; accepted: boolean };
/** Kořen požadavku ve Schránce (docs/navrhy/2026-10-31-vyslech-ve-schrance.md, řez 1): fragment a rozsah Schránky. */
export type BriefVaultLink = { fragmentId: string; scope: string };
export type BriefView = { status: string; statusText: string; tone: BriefTone; synthesis: BriefSynthesis | null;
  open: BriefOpenQuestion[]; answered: BriefAnswered[]; missing: string[]; vault: BriefVaultLink | null };

const ORIGINS: Record<string, string> = { human: "od vás", research: "z rešerše", derived: "odvozeno" };
const CHECKS: Record<string, string> = { test: "ověří test", measure: "ověří měření", observe: "ověří pozorování" };
// Co chybí do jasna: server posílá „klíč: technický popis“; člověk dostane větu, co srdce ještě musí zjistit.
const MISSING: Record<string, string> = {
  goal: "cíl jednou větou", users: "pro koho to je", acceptance: "aspoň tři ověřitelná kritéria přijetí",
  outOfScope: "hranice: co se dělat nebude", parts: "úplný seznam částí",
  dependencies: "na čem věc závisí (jiné karty nebo oblasti)", questions: "odpověď na otázku s velkým dopadem",
  assumptions: "vaše potvrzení předpokladů, na kterých srdce stojí",
};
const ORIGIN_MISSING = "aspoň jedna část z rešerše nebo odvozená, aby to nebyl jen přepis zadání";
const ANSWERS_MISSING = "vaše odpovědi na otázky výše";

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const text = (value: unknown) => typeof value === "string" && value.trim() ? value.trim() : null;
const texts = (value: unknown) => list(value).map(text).filter((item): item is string => item !== null);

/** Věta stavu: co srdce právě dělá a jestli čeká na člověka. */
export function statusText(status: string, open: number): { text: string; tone: BriefTone } {
  if (status === "clear") return { text: "Jasno. Srdce z toho může plánovat karty.", tone: "clear" };
  if (status === "grilling" && open) return { text: "Srdce potřebuje vaši odpověď, než začne plánovat.", tone: "ask" };
  if (status === "grilling") return { text: "Srdce zapracovává vaše odpovědi do pochopení.", tone: "work" };
  if (status === "research") return { text: "Srdce dohledává, jak se taková věc staví a provozuje.", tone: "work" };
  return { text: "Srdce skládá podklady k požadavku.", tone: "work" };
}

/** Řádek `missing` ze serveru → česká věta pro člověka; neznámý tvar zůstane doslova. */
export function missingText(line: string) {
  const key = line.includes(":") ? line.slice(0, line.indexOf(":")).trim() : "";
  if (key === "parts" && line.includes("origin")) return ORIGIN_MISSING;
  if (key && MISSING[key]) return MISSING[key];
  if (line.startsWith("otázky výslechu")) return ANSWERS_MISSING;
  return line;
}

function synthesis(raw: unknown): BriefSynthesis | null {
  if (!object(raw)) return null;
  const parts = list(raw.parts).filter(object).flatMap(part => {
    const value = text(part.text);
    if (!value) return [];
    const origin: BriefOrigin = part.origin === "human" || part.origin === "research" || part.origin === "derived" ? part.origin : "other";
    return [{ text: value, origin, originText: ORIGINS[origin] ?? "původ neuveden", source: origin === "human" ? null : text(part.source) }];
  });
  const acceptance = list(raw.acceptance).filter(object).flatMap(item => {
    const value = text(item.text);
    return value ? [{ text: value, checkText: CHECKS[String(item.check)] ?? null }] : [];
  });
  return { goal: text(raw.goal), users: text(raw.users), parts, acceptance, outOfScope: texts(raw.outOfScope) };
}

/** `brief` požadavku → model panelu, bez spisu `null`. Otázky bez textu nebo ID se vynechají. */
export function briefView(raw: unknown): BriefView | null {
  if (!object(raw) || typeof raw.status !== "string") return null;
  const questions = list(raw.questions).filter(object).filter(item => text(item.id) && text(item.text));
  const open = questions.filter(item => item.answer === null || item.answer === undefined).map(item => ({
    id: String(item.id), text: text(item.text)!, recommended: text(item.recommended) ?? "", why: text(item.why) ?? "" }));
  const answered = questions.filter(item => text(item.answer)).map(item => ({
    id: String(item.id), text: text(item.text)!, answer: text(item.answer)!, accepted: item.accepted === true }));
  const state = statusText(raw.status, open.length);
  const missing = raw.status === "clear" ? [] : [...new Set(texts(raw.missing).map(missingText))];
  return { status: raw.status, statusText: state.text, tone: state.tone, synthesis: synthesis(raw.synthesis), open, answered, missing,
    vault: vaultLink(raw) };
}

/** Odkaz do Schránky ze spisu (`fragmentId`, `fragmentScope`); bez kořene `null`, rozsah chybí = plátno (""). */
export function vaultLink(raw: Record<string, unknown>): BriefVaultLink | null {
  const fragmentId = text(raw.fragmentId);
  return fragmentId ? { fragmentId, scope: typeof raw.fragmentScope === "string" ? raw.fragmentScope : "" } : null;
}

/** Akce panelu, které drží rodič (`IntakePlan`): probíhající zápis, chyby podle klíče a callbacky nahoru.
 *  `onAnswer` s `answer` null = „Potvrdit doporučení“. `onOpenVault` (od App) otevře Schránku na kořeni požadavku. */
export type BriefActions = { busy: string | null; errors: Record<string, string>;
  onAnswer: (requirement: string, question: string, answer: string | null) => void; onStart: (requirement: string) => void;
  onOpenVault?: (scope: string, fragmentId: string) => void };

/** Klíč zápisu a chyby: otázka požadavku, nebo spuštění výslechu požadavku. */
export const briefKey = (requirement: string, question?: string) => question ? `brief:${requirement}:${question}` : `brief:${requirement}`;
