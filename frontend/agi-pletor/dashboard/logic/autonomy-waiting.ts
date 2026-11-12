// Část Autonomie velínu: co z agent-state projektu ještě čeká na člověka a proč, bez Reactu.
// Zdroj je `GET /api/oporahub/agent-state`: akce `blocked` s důvodem „jen člověk“ nebo „brána“ a rozhodnutí.

export type WaitingItem = { id: string; what: string; target: string; reason: string };

/** Důvody, kvůli kterým agent stojí a čeká na člověka; ostatní blokace (rozpočet, závislost) čekají na stav, ne na člověka. */
const REASONS: Record<string, string> = {
  human_only: "jen člověk – zapněte plnou autonomii",
  gate_required: "brána mozku agenta nepustí – zapněte průchod bránou",
};

const VERBS: Record<string, string> = {
  accept: "Přijetí návrhu",
  accept_baseline: "Přijetí výchozího stavu",
  review: "Kontrola výsledku",
  close_card: "Uzavření karty",
  merge: "Sloučení",
};

type Action = { id?: unknown; verb?: unknown; targetId?: unknown; status?: unknown; blockReason?: unknown };
type Decision = { actionId?: unknown; title?: unknown };

const text = (value: unknown) => (typeof value === "string" ? value : "");

/** Seznam čekajícího na člověka; cizí nebo chybějící tvar odpovědi = prázdný seznam. */
export function waitingForHuman(state: unknown): WaitingItem[] {
  const value = state && typeof state === "object" ? (state as { actions?: unknown; decisions?: unknown }) : {};
  const actions = Array.isArray(value.actions) ? (value.actions as Action[]) : [];
  const decisions = Array.isArray(value.decisions) ? (value.decisions as Decision[]) : [];
  const titles = new Map(decisions.map((item) => [text(item.actionId), text(item.title)]));
  return actions
    .filter((action) => action.status === "blocked" && text(action.blockReason) in REASONS)
    .map((action) => {
      const id = text(action.id);
      const verb = text(action.verb);
      return { id, what: titles.get(id) || VERBS[verb] || verb, target: text(action.targetId).slice(0, 8),
               reason: REASONS[text(action.blockReason)] };
    });
}

/** Jedna věta stavu: jednají agenti sami, nebo na čem stojí. */
export function autonomyVerdict(full: boolean, gate: { on: boolean; passes: boolean }): string {
  if (!full) return "Agenti čekají na člověka u přijetí, uzavření a sloučení.";
  if (gate.on && !gate.passes) return "Autonomie je zapnutá, ale brána mozku agenty nepustí k zápisu.";
  return "Agenti v projektu přijímají, uzavírají a slučují sami.";
}
