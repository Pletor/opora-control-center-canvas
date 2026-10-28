// Záložka Práce v Detailu prvku: definice hotovo, kroky plánu a stav běhu jedné karty. Vše jen ze snímku
// agent-state (`cards[]`, stejný zdroj jako tvář karty na plátně a detail karty) a z pracovního zadání
// (`spec.steps` z `GET /api/node-spec`). Výpočty nepřepisuje: definice hotovo je `dodView` detailu karty,
// stav kroků `stepRows` záložky Kroky. Bez času v Reactu: `now` dodá volající.
import type { GuardSeverity } from "@/hub/oporahub-agent-state/logic/agent-state";
import { dodView, type DodView } from "@/hub/oporahub-card-drawer/logic/card-dod";
import { statusLine, type CardEntry, type StatusLine } from "@/hub/oporahub-card-drawer/logic/card-header";
import { readSteps, type SpecDoc } from "@/hub/oporahub-card-drawer/spec-tab/logic/spec-diff";
import { STEP_WORD, stepRows, withBackendSteps, type StepRow } from "@/hub/oporahub-card-drawer/steps-tab/logic/step-status";

export type WorkRun = {
  /** Kdo kartu staví (držitel lease bez předpony `agent:`); `null` = nikdo ji nedrží. */
  holder: string | null;
  /** Lease je po termínu: kartu může převzít jiný běh. */
  expired: boolean;
  /** Krok, který právě běží (`cards[].steps.current`, jinak první nehotový krok plánu). */
  step: { id: string; title: string } | null;
  /** Otevřené nálezy strážců na kartě; `null` = žádný. */
  guards: { count: number; severity: GuardSeverity; label: string } | null;
};
/** Krok plánu se slovem stavu: první nehotový krok „běží“, jen když ho někdo staví, jinak je „na řadě“. */
export type WorkStep = StepRow & { word: string };
export type WorkView = {
  /** Karta je ve snímku agent-state; jinak je stav běhu „nenapojeno“. */
  connected: boolean;
  status: StatusLine;
  dod: DodView;
  /** Kroky plánu se stavem a slovem; `null` = zadání kroky nemá (nebo ještě není načtené). */
  steps: WorkStep[] | null;
  run: WorkRun;
};

export const GUARD_LABEL: Record<GuardSeverity, string> = { block: "blokuje", warn: "varování", info: "informace" };

/** Pohled záložky Práce. `fields` je pracovní zadání (může nést `steps`), `closed` uzavření kartu člověkem. */
export function workView(card: CardEntry | null, fields: unknown, closed: boolean, now: number): WorkView {
  const plan = readSteps(fields as SpecDoc | null);
  const results = withBackendSteps(new Map(), card?.steps?.items);
  const steps = plan ? stepRows(plan, results, card?.steps?.current ?? null) : null;
  const progress = steps ? { total: steps.length, done: steps.filter(row => row.status === "done" || row.status === "skipped").length } : null;
  const lease = card?.lease ?? null;
  const expiresAt = lease ? Date.parse(lease.expiresAt) : NaN;
  const currentId = card?.steps?.current ?? null;
  const currentRow = steps?.find(row => row.isCurrent) ?? null;
  const step = currentId ? { id: currentId, title: steps?.find(row => row.id === currentId)?.title ?? "" }
    : lease && currentRow ? { id: currentRow.id, title: currentRow.title } : null;
  const guards = card?.guardFindings && card.guardFindings.count > 0
    ? { ...card.guardFindings, label: GUARD_LABEL[card.guardFindings.severity] } : null;
  return {
    connected: card !== null,
    status: statusLine(card),
    dod: dodView({ card, steps: progress, closed }),
    steps: steps?.map(row => ({ ...row, word: row.status === "current" && step?.id !== row.id ? "na řadě" : STEP_WORD[row.status] })) ?? null,
    run: {
      holder: lease?.holder ? lease.holder.replace(/^agent:/, "") : null,
      expired: Number.isFinite(expiresAt) && expiresAt <= now,
      step,
      guards,
    },
  };
}
