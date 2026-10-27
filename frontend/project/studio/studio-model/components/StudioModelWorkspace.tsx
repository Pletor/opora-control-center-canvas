import { useEffect, useMemo, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import { proposeModelFromArchitecture } from "../../model/logic/model-proposal";
import type { Point } from "../../model/logic/model-types";
import { withSimulationDefaults } from "../../model/simulation/logic/model-adapter";
import type { BindingCard } from "../../studio-layer/logic/studio-layer";
import { portClick, type Link, type PendingPort } from "../../studio-model-canvas/logic/connect-gesture";
import StudioModelCanvas from "../../studio-model-canvas/components/StudioModelCanvas";
import ModelPalette from "../../studio-model-palette/components/ModelPalette";
import ModelInspector, { type InspectorActions } from "../../studio-model-inspector/components/ModelInspector";
import { addNode, connectPorts, moveNode, removeSelected, renameNode, setBinding, setParameter, updateEdge, type Selection } from "../logic/model-edit";
import { modelKey } from "../logic/model-save";
import { counted, unresolvedRows, type UnresolvedRow } from "../logic/proposal-rows";
import { useModelEditor } from "../logic/use-model-editor";
import ModelToolbar from "./ModelToolbar";
import ModelEmptyOffer from "./ModelEmptyOffer";
import ModelUnresolved from "./ModelUnresolved";
import "../styles/studio-model.css";

const COMPONENTS = ["komponenta", "komponenty", "komponent"] as const, LINKS = ["vazba", "vazby", "vazeb"] as const;

type Props = { project: string; domainId: string; domainName: string; graph: Graph; bindings: BindingCard[] };

const editingTarget = (target: EventTarget | null) => target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement
  || target instanceof HTMLSelectElement || (target instanceof HTMLElement && target.isContentEditable);

/** Vrstva MODEL jedné domény (docs/studio.md §1, §3, §4; etapa S6a), načtená líně. Rodič editace: skládá katalog vlevo,
 * lištu s uložením, plátno a inspektor vpravo; drží editor modelu (historie, revize, uložení), výběr, rozdělanou
 * vazbu a krátké hlášky. Jediné místo, které model ukládá (`useModelEditor` → `PUT /api/studio/model`). */
export default function StudioModelWorkspace({ project, domainId, domainName, graph, bindings }: Props) {
  const editor = useModelEditor(project, domainId);
  const { model, apply } = editor;
  const [selection, setSelection] = useState<Selection>(null);
  const [pending, setPending] = useState<PendingPort | null>(null);
  const [toast, setToast] = useState("");
  const [unresolved, setUnresolved] = useState<UnresolvedRow[]>([]);
  const [started, setStarted] = useState(false);
  const bindingMap = useMemo(() => new Map(bindings.map((card) => [card.id, card])), [bindings]);
  const selected: Selection = selection && (selection.kind === "node" ? model.nodes : model.edges).some((item) => item.id === selection.id) ? selection : null;

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

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
  const actions: InspectorActions = {
    onRename: (id, name) => apply((current) => renameNode(current, id, name), "name:" + id),
    onBinding: (id, cardId) => apply((current) => setBinding(current, id, cardId)),
    onParameter: (id, key, value) => apply((current) => setParameter(current, id, key, value)),
    onEdge: (id, patch) => apply((current) => updateEdge(current, id, patch), "enabled" in patch ? null : `edge:${id}:${Object.keys(patch).join()}`),
    onDelete: remove,
    onClear: () => setSelection(null),
  };
  const offer = editor.status === "ready" && !model.nodes.length && !started;
  return <div className="studio-model" data-testid="studio-model">
    <ModelPalette onAdd={(typeId) => add(typeId)}/>
    <div className="studio-model__stage">
      <ModelToolbar editor={editor} domainName={domainName} nodes={model.nodes.length} edges={model.edges.length}/>
      <div className="studio-model__board">
        <StudioModelCanvas model={model} bindings={bindingMap} selection={selected} pending={pending}
          onSelect={(next) => { setSelection(next); if (!next) setPending(null); }} onMove={(id, position) => apply((current) => moveNode(current, id, position))}
          onAdd={add} onPortClick={(port) => { const result = portClick(pending, port); setPending(result.pending); if (result.link) link(result.link); }}
          onLink={(next) => { setPending(null); link(next); }} onMessage={setToast}/>
        {offer && <ModelEmptyOffer domainName={domainName} cards={bindings.length} onPropose={propose} onEmpty={() => setStarted(true)}/>}
        {toast && <p className="studio-model__toast" role="status" data-testid="studio-model-toast">{toast}</p>}
      </div>
      {unresolved.length > 0 && <ModelUnresolved rows={unresolved} onClose={() => setUnresolved([])}/>}
    </div>
    <ModelInspector model={model} selection={selected} bindings={bindings} actions={actions}/>
  </div>;
}
