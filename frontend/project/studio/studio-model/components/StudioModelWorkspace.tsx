import { useCallback, useEffect, useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import { proposeModelFromArchitecture } from "../../model/logic/model-proposal";
import type { Point } from "../../model/logic/model-types";
import { withSimulationDefaults } from "../../model/simulation/logic/model-adapter";
import type { Scenario } from "../../model/simulation/logic";
import type { BindingCard } from "../../studio-layer/logic/studio-layer";
import { portClick, type Link, type PendingPort } from "../../studio-model-canvas/logic/connect-gesture";
import StudioModelCanvas from "../../studio-model-canvas/components/StudioModelCanvas";
import ModelPalette from "../../studio-model-palette/components/ModelPalette";
import ModelInspector, { type InspectorActions } from "../../studio-model-inspector/components/ModelInspector";
import ModelRunBar from "../../studio-model-run/components/ModelRunBar";
import { incidentNodes } from "../../studio-model-run/logic/run-control";
import { cardRuns, linkFlows } from "../../studio-model-run/logic/run-view";
import { planIncident, unplanIncident } from "../../studio-model-run/logic/incident-plan";
import { useModelRun } from "../../studio-model-run/logic/use-model-run";
import ModelTelemetry from "../../studio-model-telemetry/components/ModelTelemetry";
import type { IncidentActions } from "../../studio-model-telemetry/components/IncidentControls";
import ScenarioLibrary from "../../studio-model-scenarios/components/ScenarioLibrary";
import { addNode, connectPorts, moveNode, removeSelected, renameNode, setBinding, setParameter, updateEdge, type Selection } from "../logic/model-edit";
import { modelKey } from "../logic/model-save";
import { counted, unresolvedRows, type UnresolvedRow } from "../logic/proposal-rows";
import { useModelDomain, useScenarioSeed } from "../logic/use-model-domain";
import { useModelEditor } from "../logic/use-model-editor";
import ModelToolbar from "./ModelToolbar";
import ModelEmptyOffer from "./ModelEmptyOffer";
import ModelUnresolved from "./ModelUnresolved";
import "../styles/studio-model.css";

const COMPONENTS = ["komponenta", "komponenty", "komponent"] as const, LINKS = ["vazba", "vazby", "vazeb"] as const;

type Props = { project: string; domainId: string; domainName: string; graph: Graph; bindings: BindingCard[] };

const editingTarget = (target: EventTarget | null) => target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement
  || target instanceof HTMLSelectElement || (target instanceof HTMLElement && target.isContentEditable);

/** Vrstva MODEL jedné domény (docs/studio.md §1, §3–5; etapy S6a, S6b), načtená líně. Rodič: skládá katalog vlevo,
 * lištu s uložením a lištu RUN, plátno s částicemi a inspektor s telemetrií vpravo; drží editor modelu (historie,
 * revize, uložení), běh simulace, modelovou doménu (architektura nebo scénář), výběr, rozdělanou vazbu a hlášky.
 * Jediné místo, které model ukládá (`useModelEditor` → `PUT /api/studio/model`); běh nic neukládá. */
export default function StudioModelWorkspace({ project, domainId, domainName, graph, bindings }: Props) {
  const domain = useModelDomain(domainId, domainName);
  const editor = useModelEditor(project, domain.id);
  const { model, apply } = editor;
  const [selection, setSelection] = useState<Selection>(null);
  const [pending, setPending] = useState<PendingPort | null>(null);
  const [toast, setToast] = useState("");
  const [unresolved, setUnresolved] = useState<UnresolvedRow[]>([]);
  const [started, setStarted] = useState(false);
  const [library, setLibrary] = useState(false);
  const runner = useModelRun(model, setToast);
  const { run } = runner;
  const cardBindings = useMemo(() => domain.scenario ? [] : bindings, [domain.scenario, bindings]);
  const bindingMap = useMemo(() => new Map(cardBindings.map((card) => [card.id, card])), [cardBindings]);
  const runs = useMemo(() => cardRuns(run.sim), [run.sim]), flows = useMemo(() => linkFlows(run.sim), [run.sim]);
  const frame = useMemo(() => ({ running: run.running, tick: run.sim.tick, key: domain.id }), [run.running, run.sim.tick, domain.id]);
  const selected: Selection = selection && (selection.kind === "node" ? model.nodes : model.edges).some((item) => item.id === selection.id) ? selection : null;

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  useScenarioSeed(editor, domain.scenario, domain.id, useCallback((fresh: boolean) => setToast(fresh
    ? "Scénář je otevřený v nové modelové doméně (neuloženo). Model domény architektury zůstal beze změny."
    : "Doména scénáře už je uložená: otevřena uložená verze, scénář ji nepřepsal."), []));

  const remove = () => { if (selected) { apply((current) => removeSelected(current, selected)); setSelection(null); } };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const key = modelKey(event, editingTarget(event.target));
      if (!key) return;
      event.preventDefault();
      if (key === "undo") editor.undo();
      else if (key === "redo") editor.redo();
      else if (key === "delete") remove();
      else { setPending(null); setSelection(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const add = (typeId: string, position?: Point) => {
    const id = globalThis.crypto.randomUUID();
    apply((current) => addNode(current, typeId, position, id).model);
    setSelection({ kind: "node", id });
    setStarted(true);
  };
  const link = ({ from, to }: Link) => {
    const result = connectPorts(model, from, to);
    if ("error" in result) { setToast(result.error); return; }
    apply(() => result.model);
    setSelection({ kind: "edge", id: result.edgeId });
    setToast("Kompatibilní vazba byla vytvořena.");
  };
  const propose = () => {
    const proposal = proposeModelFromArchitecture(graph, domainId);
    apply((current) => ({ ...current, nodes: proposal.model.nodes.map((node) => withSimulationDefaults(node)), edges: proposal.model.edges }));
    setUnresolved(unresolvedRows(graph, proposal.unresolved));
    setStarted(true);
    setToast(`Návrh z architektury: ${counted(proposal.model.nodes.length, COMPONENTS)}, ${counted(proposal.model.edges.length, LINKS)}. Zkontrolujte a uložte.`);
  };
  const leave = (go: () => void) => {
    if (editor.dirty && !window.confirm("Model má neuložené změny; přepnutím modelové domény se zahodí. Pokračovat?")) return;
    runner.reset(); setSelection(null); setPending(null); setUnresolved([]); setLibrary(false); go();
  };
  const openScenario = (scenario: Scenario) => leave(() => domain.open(scenario));
  const actions: InspectorActions = {
    onRename: (id, name) => apply((current) => renameNode(current, id, name), "name:" + id),
    onBinding: (id, cardId) => apply((current) => setBinding(current, id, cardId)),
    onParameter: (id, key, value) => apply((current) => setParameter(current, id, key, value)),
    onEdge: (id, patch) => apply((current) => updateEdge(current, id, patch), "enabled" in patch ? null : `edge:${id}:${Object.keys(patch).join()}`),
    onDelete: remove,
    onClear: () => setSelection(null),
  };
  const incidents: IncidentActions = {
    onIncident: (kind, nodeId) => { runner.command(kind, [nodeId]); setToast(`MODEL · ${kind} – nezasahuje do skutečných služeb.`); },
    onPlan: (kind, nodeId, tick) => {
      const result = planIncident(model, kind, nodeId, tick);
      if ("error" in result) return result.error;
      apply(() => result.model);
      setToast(`Plánovaný incident ${kind} v ticku ${tick} je v modelu; uloží se tlačítkem Uložit.`);
      return null;
    },
    onUnplan: (index, nodeId) => apply((current) => unplanIncident(current, index, nodeId)),
  };
  const offer = editor.status === "ready" && !model.nodes.length && !started && !domain.scenario;
  return <div className="studio-model" data-testid="studio-model" data-model-domain={domain.id}>
    <ModelPalette onAdd={(typeId) => add(typeId)}/>
    <div className="studio-model__stage">
      <ModelToolbar editor={editor} domainName={domain.name} nodes={model.nodes.length} edges={model.edges.length}
        back={domain.scenario ? { label: domain.architecture, onBack: () => leave(domain.back) } : undefined}/>
      <ModelRunBar run={run} model={model} actions={{
        onStart: runner.start, onPause: runner.pause, onStep: runner.step, onReset: runner.reset, onSpeed: runner.setSpeed,
        onSurge: () => runner.command("surge"), onRestoreAll: () => { if (incidentNodes(run.sim).length) runner.command("restore-all"); }, onScenarios: () => setLibrary(true),
      }}/>
      <div className="studio-model__board">
        <StudioModelCanvas model={model} bindings={bindingMap} selection={selected} pending={pending} frame={frame} runs={runs} flows={flows}
          onSelect={(next) => { setSelection(next); if (!next) setPending(null); }} onMove={(id, position) => apply((current) => moveNode(current, id, position))}
          onAdd={add} onPortClick={(port) => { const result = portClick(pending, port); setPending(result.pending); if (result.link) link(result.link); }}
          onLink={(next) => { setPending(null); link(next); }} onMessage={setToast}/>
        {offer && !library && <ModelEmptyOffer domainName={domain.name} cards={bindings.length} onPropose={propose} onEmpty={() => setStarted(true)} onScenarios={() => setLibrary(true)}/>}
        {library && <ScenarioLibrary onOpen={openScenario} onClose={() => setLibrary(false)}/>}
        {toast && <p className="studio-model__toast" role="status" data-testid="studio-model-toast">{toast}</p>}
      </div>
      {unresolved.length > 0 && <ModelUnresolved rows={unresolved} onClose={() => setUnresolved([])}/>}
    </div>
    <ModelInspector model={model} selection={selected} bindings={cardBindings} actions={actions}
      telemetry={<ModelTelemetry model={model} selection={selected} run={run} actions={incidents}/>}/>
  </div>;
}
