// Pohled „Požadavky a plán“ ve Velínu (docs/navrhy/2026-10-30-vstupni-brana.md §6, metriky-a-spoustece.md §7 řez 4)
// nad `GET /api/intake?project=&workspace=`: souhrn vstupů a jeden dílek na oblast (aktivní milník s postupem
// a kritérii, návrhy srdce, otevřené a odložené požadavky, u každého výslech srdce `brief`, řez 3 výslechu).
// Čistá funkce: jména karet dodá volající z grafu.
import { briefView, type BriefView } from "../brief-panel/logic/brief-model";

export type IntakeCriterion = { id: string; text: string; cards: (string | { id: string; done: boolean })[]; done?: boolean };
export type IntakeMilestone = { id: string; title: string; criteria: IntakeCriterion[]; status: string; progress?: number; done?: boolean;
  closureProgress?: number; verification?: { verified: boolean; independent?: boolean; source?: string; acceptedRevision?: string; headSha?: string } };
export type IntakeRequirement = { id: string; title: string; status: string; openCondition: string | null; milestoneId: string | null;
  brief?: unknown };
export type IntakeArea = { id: string; name: string; milestone: IntakeMilestone | null; proposed: IntakeMilestone[];
  requirements: IntakeRequirement[]; deferred: IntakeRequirement[] };
export type IntakeEntry = { id: string; layer: string; verdict: string };
export type IntakeResponse = { areas: IntakeArea[]; unassigned: IntakeRequirement[]; entries: IntakeEntry[]; pending: number; duplicates: number };

export type PlanCard = { id: string; name: string; done: boolean | null };
export type PlanCriterion = { id: string; text: string; done: boolean | null; cards: PlanCard[] };
export type PlanMilestone = { id: string; title: string; progress: number | null; done: boolean; criteria: PlanCriterion[] };
export type PlanRequirement = { id: string; title: string; condition: string | null; brief: BriefView | null };
export type PlanArea = { id: string; name: string; empty: boolean; milestone: PlanMilestone | null; proposed: PlanMilestone[];
  requirements: PlanRequirement[]; deferred: PlanRequirement[] };
export type PlanSummary = { entries: number; fresh: number; pending: number; duplicates: number };
export type IntakePlan = { summary: PlanSummary; areas: PlanArea[]; unassigned: PlanRequirement[] };

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const list = (value: unknown) => Array.isArray(value) ? value : [];
const count = (value: unknown) => typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 0;

/** Ověří kostru odpovědi (oblasti a počty); neplatná odpověď hází českou chybu, vnitřní pole se čtou opatrně. */
export function parseIntake(raw: unknown): IntakeResponse {
  if (!object(raw) || !Array.isArray(raw.areas) || !raw.areas.every(area => object(area) && typeof area.id === "string"))
    throw new Error("Požadavky a plán: server vrátil neplatnou odpověď.");
  return raw as unknown as IntakeResponse;
}

function milestone(item: IntakeMilestone, nameOf: (id: string) => string): PlanMilestone {
  const criteria = list(item.criteria).map((criterion: IntakeCriterion) => ({
    id: criterion.id, text: criterion.text, done: typeof criterion.done === "boolean" ? criterion.done : null,
    cards: list(criterion.cards).map(card => typeof card === "string" ? { id: card, name: nameOf(card), done: null }
      : { id: card.id, name: nameOf(card.id), done: Boolean(card.done) }),
  }));
  const progress = typeof item.progress === "number" ? Math.max(0, Math.min(100, Math.round(item.progress))) : null;
  return { id: item.id, title: item.title, progress, done: item.done === true, criteria };
}

/** Odpověď → model pohledu. `nameOf` dá jméno karty (uzlu) z grafu, jinak ID. Podmínka otevření `ms_…` se přeloží
 *  na název milníku, který pohled zná (aktivní nebo navržený); jiný text zůstává, jak ho zapsalo srdce. */
export function intakePlan(data: IntakeResponse, nameOf: (id: string) => string): IntakePlan {
  const titles = new Map<string, string>();
  for (const area of data.areas) for (const item of [area.milestone, ...list(area.proposed)]) if (item) titles.set(item.id, item.title);
  const requirement = (item: IntakeRequirement): PlanRequirement => ({ id: item.id, title: item.title,
    condition: item.openCondition ? (titles.has(item.openCondition) ? `otevře se po splnění milníku „${titles.get(item.openCondition)}“` : `podmínka otevření: ${item.openCondition}`) : null,
    brief: briefView(item.brief) });
  const areas = data.areas.map(area => {
    const plan = { id: area.id, name: area.name || area.id, milestone: area.milestone ? milestone(area.milestone, nameOf) : null,
      proposed: list(area.proposed).map(item => milestone(item, nameOf)), requirements: list(area.requirements).map(requirement),
      deferred: list(area.deferred).map(requirement) };
    return { ...plan, empty: !plan.milestone && !plan.proposed.length && !plan.requirements.length && !plan.deferred.length };
  });
  const entries = list(data.entries) as IntakeEntry[];
  return { areas, unassigned: list(data.unassigned).map(requirement),
    summary: { entries: entries.length, fresh: entries.filter(entry => entry.layer !== "heart").length,
      pending: count(data.pending), duplicates: count(data.duplicates) } };
}

const plural = (value: number, one: string, few: string, many: string) => `${value} ${value === 1 ? one : value > 1 && value < 5 ? few : many}`;

/** Řádek souhrnu nahoře: nové vstupy (srdce je ještě nepotvrdilo), čekající stanoviska a duplicity. */
export function summaryParts(summary: PlanSummary) {
  return [
    { key: "fresh", text: plural(summary.fresh, "nový vstup", "nové vstupy", "nových vstupů"), value: summary.fresh },
    { key: "pending", text: `${summary.pending} čeká na stanovisko`, value: summary.pending },
    { key: "duplicates", text: plural(summary.duplicates, "duplicita", "duplicity", "duplicit"), value: summary.duplicates },
  ];
}

export const criteriaDone = (item: PlanMilestone) => `${item.criteria.filter(criterion => criterion.done).length}/${item.criteria.length} kritérií`;
