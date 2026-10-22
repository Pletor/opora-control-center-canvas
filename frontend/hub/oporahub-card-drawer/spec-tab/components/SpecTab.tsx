import { useRef, useState } from "react";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { CardData } from "../../logic/use-card-data";
import type { DrawerEditor } from "../../logic/drawer-editor";
import { specDiff } from "../logic/spec-diff";
import SpecDiff, { type SpecMode } from "./SpecDiff";
import SpecPending from "./SpecPending";
import SpecProposal from "./SpecProposal";
import SpecEditors from "./SpecEditors";
import "../styles/spec-tab.css";

type Props = { project: string; workspace: string; nodeId: string; node: CanvasNode | null; data: CardData; editor: DrawerEditor | null };
const MODES: { key: SpecMode; label: string }[] = [{ key: "accepted", label: "Přijaté" }, { key: "working", label: "Pracovní" }, { key: "diff", label: "Rozdíl" }];

/** Záložka Zadání: přijaté proti pracovnímu (cíl, ne-cíle, akceptace, kroky), čekající návrhy a návrh změny. */
export default function SpecTab({ project, workspace, nodeId, node, data, editor }: Props) {
  const view = specDiff(data.accepted?.fields ?? null, data.working?.fields ?? null);
  const [mode, setMode] = useState<SpecMode>("diff");
  const lastStored = useRef("");
  const head = data.context?.acceptedHead ?? null;
  const lastAccepted = data.changesets.filter(item => item.accepted).at(-1);
  const conflicts = (data.agent?.actions ?? []).filter(item => item.verb === "proposal.resolve_conflict").length;
  const running = data.latest?.state === "running";
  function specSaved(stored: { fields: unknown }) {
    if (!stored.fields) return;
    const text = JSON.stringify(stored.fields);
    if (lastStored.current && text !== lastStored.current) data.reload();
    lastStored.current = text;
  }
  return <div className="spec-tab" data-oh-view="card-spec" data-oh-node-id={nodeId} data-oh-accepted-head={head ?? ""}
    data-oh-working-differs={String(view.changes > 0)}>
    <div className="spec-tab__bar">
      <span className="spec-tab__chip spec-tab__chip--acc" data-oh-field="accepted-revision" data-oh-value={data.accepted ? head ?? "" : ""}>
        {data.accepted ? `přijato ${head?.slice(0, 8) ?? "?"}` : "◌ nepřijato"}</span>
      <span className="spec-tab__muted">{lastAccepted ? `${lastAccepted.createdAt.slice(0, 16).replace("T", " ")} · ${lastAccepted.by.name}` : data.context ? "bez přijaté změny v historii" : "načítám…"}</span>
      <div className="spec-tab__modes" role="group" aria-label="Pohled na zadání">
        {MODES.map(item => <button key={item.key} type="button" aria-pressed={mode === item.key} className="spec-tab__mode"
          onClick={() => setMode(item.key)}>{item.label}</button>)}
      </div>
    </div>
    {!data.context && !data.busy && <p className="spec-tab__muted">◌ Kontext zadání OporaHubu není dostupný.</p>}
    <SpecDiff view={view} mode={mode} purpose={node?.purpose ?? ""} />
    {running && <p className="spec-tab__info" data-oh-field="snapshot-note">
      <b aria-hidden="true">i</b> Běžící exekuce pracuje se snímkem přijaté revize {data.latest?.acceptedRevision.slice(0, 8)}. Po přijetí nové verze se
      pracovní změny automaticky rebasují; konflikt by vytvořil rozhodnutí pro člověka.</p>}
    <SpecPending project={project} workspace={workspace} items={data.changesets} acceptedHead={head} conflicts={conflicts} onChanged={data.reload} />
    {node && editor && <SpecEditors project={project} workspace={workspace} node={node} editor={editor} onSpecSaved={specSaved} />}
    <SpecProposal project={project} workspace={workspace} context={data.context} working={data.working} accepted={data.accepted}
      changes={view.changes} readOnly={!editor || editor.readOnly} onChanged={data.reload} />
  </div>;
}
