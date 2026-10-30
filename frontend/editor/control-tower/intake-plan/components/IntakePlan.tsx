// Pohled „Požadavky a plán“ ve Velínu (docs/navrhy/2026-10-30-vstupni-brana.md §6): nahoře souhrn vstupů, pod ním
// jeden dílek na oblast a nakonec požadavky bez oblasti. Rodič pohledu: čte `GET /api/intake`, drží probíhající
// zápis a chyby. Rozhodnutí člověka o návrhu milníku posílá `POST /api/intake/milestone`, odpověď na výslech srdce
// `POST /api/intake/brief/answer` a „Vyslechni mě k tomu“ `POST /api/intake/brief/start`; po úspěchu načte znovu.
import { useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { intakePlan } from "../logic/intake-plan";
import { answerBrief, briefError, decideMilestone, decisionError, startBrief, type MilestoneAction } from "../logic/intake-api";
import { useIntakePlan } from "../logic/use-intake-plan";
import { briefKey, type BriefActions } from "../brief-panel/logic/brief-model";
import IntakeArea from "./IntakeArea";
import IntakeRequirements from "./IntakeRequirements";
import IntakeSummary from "./IntakeSummary";
import "../styles/intake-plan.css";

type Props = { project: string; workspace: string; graph: Graph; onOpen: (nodeId: string) => void };

export default function IntakePlan({ project, workspace, graph, onOpen }: Props) {
  const intake = useIntakePlan(project, workspace);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const plan = useMemo(() => {
    if (!intake.data) return null;
    const names = new Map(graph.nodes.map(node => [node.id, node.name]));
    return intakePlan(intake.data, id => names.get(id) || id);
  }, [intake.data, graph]);

  // Jeden zápis najednou: klíč drží `busy`, chyba se uloží pod stejný klíč a úspěch načte pohled znovu.
  const write = async (key: string, send: () => Promise<unknown>, fail: (error: unknown) => string) => {
    if (busy) return;
    setBusy(key);
    setErrors(previous => { const rest = { ...previous }; delete rest[key]; return rest; });
    try {
      await send();
      intake.reload();
    } catch (error) {
      setErrors(previous => ({ ...previous, [key]: fail(error) }));
    } finally {
      setBusy(null);
    }
  };
  const decide = (milestoneId: string, action: MilestoneAction) =>
    write(milestoneId, () => decideMilestone(project, workspace, milestoneId, action), error => decisionError(action, error));
  const brief: BriefActions = { busy, errors,
    onAnswer: (requirement, question, answer) => write(briefKey(requirement, question),
      () => answerBrief(project, workspace, requirement, question, answer), error => briefError("answer", error)),
    onStart: requirement => write(briefKey(requirement), () => startBrief(project, workspace, requirement),
      error => briefError("start", error)) };

  return (
    <section className="intake-plan" aria-label="Požadavky a plán" data-oh-view="velin-plan">
      <JsonMirror id="oh-velin-plan" value={plan} />
      {intake.error && <p className="intake-plan__error" role="alert">{intake.error}</p>}
      {!plan && !intake.error && <p className="intake-plan__muted">Načítám požadavky a plán…</p>}
      {plan && <>
        <IntakeSummary summary={plan.summary} />
        {!plan.areas.length && <p className="intake-plan__muted">Plátno tohoto prostoru zatím nemá žádnou oblast. Požadavky a milníky se vážou na oblasti.</p>}
        <div className="intake-plan__areas">
          {plan.areas.map(area => <IntakeArea key={area.id} area={area} busy={busy} errors={errors} onDecide={decide} onOpen={onOpen} brief={brief} />)}
        </div>
        <IntakeRequirements title="Požadavky bez oblasti" items={plan.unassigned} brief={brief} />
      </>}
    </section>
  );
}
