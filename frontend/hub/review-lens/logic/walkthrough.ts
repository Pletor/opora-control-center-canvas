import type { GraphDoc } from "@coldtea/pr-lens-schema";
import type { Box } from "./overlay";

// Plátna a průvodce Lens bez Reactu. Plátno („stage“) je jeden obrázek rendereru: pohled ze specu
// (`views`, architektura nebo tok dat), celá čočka, když pohledy chybí, nebo jeden tok, na který
// míří krok průvodce. Krok průvodce vybere plátno a prvky, které se orámují (`focus` → rámečky atlasu).
export type Lens = "architecture" | "data-flow";
export type Stage = { key: string; label: string; lens: Lens; view?: string; flow?: string };
export type Atlas = { lanes: Record<string, Box>; nodes: Record<string, Box>; edges: Record<string, Box>; messages: Record<string, Record<string, Box>> };
export type Step = NonNullable<GraphDoc["walkthrough"]>["steps"][number];

const LENS_LABEL: Record<Lens, string> = { architecture: "Architektura", "data-flow": "Tok dat" };

function flatViews(views: GraphDoc["views"]): GraphDoc["views"] {
  return views.flatMap(view => [view, ...flatViews(view.children)]);
}

/** Přepínač plátna: pohledy dokumentu (jen deklarované čočky), jinak jedna položka na čočku. */
export function stagesOf(doc: GraphDoc): Stage[] {
  const views = flatViews(doc.views).filter(view => doc.lenses.includes(view.lens));
  if (views.length) return views.map(view => ({ key: `view:${view.id}`, label: view.title, lens: view.lens, view: view.id }));
  return doc.lenses.filter(lens => lens !== "data-flow" || doc.flows.length > 0)
    .map(lens => ({ key: `lens:${lens}`, label: LENS_LABEL[lens], lens }));
}

/** Plátno kroku: jeho pohled, tok (pohled, který ukazuje jen ten tok, jinak tok samotný), nebo to současné. */
export function stepStage(doc: GraphDoc, step: Step, current: Stage, stages: readonly Stage[]): Stage {
  const stage = step.stage;
  if (!stage) return current;
  if (stage.kind === "view") return stages.find(item => item.view === stage.view) ?? current;
  const flow = doc.flows.find(item => item.id === stage.flow);
  if (!flow) return current;
  const own = stages.find(item => {
    const view = item.view ? flatViews(doc.views).find(candidate => candidate.id === item.view) : undefined;
    return view?.lens === "data-flow" && view.scope.kind === "selection" && view.scope.flows.length === 1 && view.scope.flows[0] === flow.id;
  });
  return own ?? { key: `flow:${flow.id}`, label: flow.title, lens: "data-flow", flow: flow.id };
}

/** Rámečky, na které krok míří; `all` znamená celé plátno (prázdný seznam). Neznámá id se tiše vynechají. */
export function focusBoxes(step: Step, atlas: Atlas, flow: string | null): Box[] {
  const focus = step.focus;
  if (focus.kind !== "selection") return [];
  const pick = (ids: readonly string[] | undefined, table: Record<string, Box> | undefined) =>
    (ids ?? []).flatMap(id => table?.[id] ? [table[id]] : []);
  const messages = flow ? pick(focus.messages, atlas.messages[flow])
    : (focus.messages ?? []).flatMap(id => Object.values(atlas.messages).flatMap(steps => steps[id] ? [steps[id]] : []));
  return [...pick(focus.lanes, atlas.lanes), ...pick(focus.nodes, atlas.nodes), ...pick(focus.edges, atlas.edges), ...messages];
}

/** Tok, jehož kroky plátno kreslí (pro klíč `messages` v atlasu): plátno toku, nebo krok míří na tok. */
export function stageFlow(stage: Stage, step: Step | null): string | null {
  if (stage.flow) return stage.flow;
  return step?.stage?.kind === "flow" ? step.stage.flow : null;
}

// Stav přehrávače: index kroku, nebo -1 = průvodce neběží. `W`/→ další, ← zpět, Esc stop.
export type Walk = { index: number };
export type WalkAction = "start" | "next" | "prev" | "stop";

export function walkReducer(state: Walk, action: WalkAction, total: number): Walk {
  if (total <= 0) return { index: -1 };
  switch (action) {
    case "start": return { index: state.index >= 0 ? state.index : 0 };
    case "next": return { index: state.index < 0 ? 0 : Math.min(total - 1, state.index + 1) };
    case "prev": return { index: state.index <= 0 ? state.index : state.index - 1 };
    case "stop": return { index: -1 };
  }
}

/** Klávesa → akce průvodce; šipky a Esc jen při běžícím průvodci, aby nebraly šipky záložkám. */
export function walkKey(key: string, active: boolean): WalkAction | null {
  if (key === "w" || key === "W") return "next";
  if (!active) return null;
  return key === "ArrowRight" ? "next" : key === "ArrowLeft" ? "prev" : key === "Escape" ? "stop" : null;
}
