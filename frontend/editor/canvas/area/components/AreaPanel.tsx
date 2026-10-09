// Inspektor oblasti: jméno, účel, ke čtení seznam karet uvnitř a toků do/z jiných oblastí, na konci
// smazání. Dílek nic neukládá — rozepsané pole drží u sebe a po opuštění (blur) hotovou hodnotu
// ohlásí nahoru přes onSave(node), stejně jako NodePanel a CommentPanel. Členy a toky spočítá rodič
// (App) z grafu — tenhle dílek je jen vypíše a klik na člena předá dál přes onOpenNode.
import { useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import type { CanvasNode } from "@/shared/types/logic/types";
import { AREA_COLORS, areaColorOf, setAreaColor } from "@/editor/canvas/area/logic/area-model";
import AgentWorkspace from "@/editor/node-detail/agent-workspace/components/AgentWorkspace";
import "@/editor/canvas/area/styles/area.css";

const KIND_LABEL: Record<string, string> = { node: "Uzel", sector: "Sektor", comment: "Komentář" };

export type AreaMember = { id: string; name: string; kind: string };
export type AreaFlow = { id: string; name: string; direction: "in" | "out" };

export default function AreaPanel({
  project,
  workspace,
  node,
  readOnly,
  /** Uzavřená karta (done.confirmed): pracovní prostor agenta se pak nezapisuje, i když main jinak píše. */
  closed,
  busy,
  members,
  flows,
  onSave,
  onOpenNode,
  onDelete,
}: {
  project: string;
  workspace: string;
  node: CanvasNode;
  readOnly: boolean;
  closed: boolean;
  busy: boolean;
  members: AreaMember[];
  flows: AreaFlow[];
  onSave: (n: CanvasNode) => void;
  onOpenNode: (id: string) => void;
  onDelete: () => void;
}) {
  const [name, setName] = useState(node.name);
  const [purpose, setPurpose] = useState(node.purpose);
  useScopedSaveParticipant({ id: `area-fields:${node.id}`, label: `Oblast: ${node.name || node.id}`,
    dirty: name.trim() !== node.name || purpose !== node.purpose,
    blocked: "Dokončete úpravu názvu nebo účelu oblasti a vyčkejte na její uložení." });
  return (
    <div className="area-panel" data-testid="area-panel">
      <div className="eyebrow">OBLAST</div>
      <label className="field">
        Název
        <input
          aria-label="Název oblasti"
          value={name}
          maxLength={160}
          readOnly={readOnly}
          placeholder="Pojmenujte oblast, až bude mít účel"
          onChange={(e) => setName(e.target.value)}
          onBlur={() => {
            const next = name.trim();
            if (next !== node.name) onSave({ ...node, name: next });
          }}
        />
      </label>
      <label className="field">
        Účel
        <textarea
          aria-label="Účel oblasti"
          rows={5}
          maxLength={4000}
          value={purpose}
          readOnly={readOnly}
          placeholder="K čemu oblast slouží"
          onChange={(e) => setPurpose(e.target.value)}
          onBlur={() => { if (purpose !== node.purpose) onSave({ ...node, purpose }); }}
        />
      </label>
      <div className="area-panel__swatches" role="group" aria-label="Barva oblasti">
        {AREA_COLORS.map((c) => (
          <button
            key={c.value}
            type="button"
            className={"area-panel__swatch" + (areaColorOf(node) === c.value ? " area-panel__swatch--active" : "")}
            data-color={c.value}
            data-testid={"area-swatch-" + c.value}
            aria-label={c.label}
            title={c.label}
            disabled={readOnly || busy}
            onClick={() => onSave(setAreaColor(node, c.value))}
          />
        ))}
      </div>
      <AgentWorkspace
        key={project + ":" + workspace + ":" + node.id}
        project={project}
        workspace={workspace}
        nodeId={node.id}
        readOnly={readOnly || closed}
      />
      <h3>Karty uvnitř{members.length ? ` (${members.length})` : ""}</h3>
      {members.length ? (
        <ul className="area-panel__members" data-testid="area-panel-members">
          {members.map((m) => (
            <li key={m.id}>
              <button type="button" className="quiet" onClick={() => onOpenNode(m.id)}>
                <span className="area-panel__member-kind">{KIND_LABEL[m.kind] ?? m.kind}</span> {m.name}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Žádná karta zatím nemá střed uvnitř tohoto rámu.</p>
      )}
      <h3>Tok do / z jiných oblastí</h3>
      {flows.length ? (
        <ul className="area-panel__flows" data-testid="area-panel-flows">
          {flows.map((f) => (
            <li key={f.id}>
              <span className={"area-panel__flow-dir area-panel__flow-dir--" + f.direction}>{f.direction === "in" ? "←" : "→"}</span> {f.name}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Žádný tok do jiné oblasti.</p>
      )}
      <p className="muted area-panel__note">
        Co má střed uvnitř rámu, do oblasti patří. Model to dostane v node-brief jako context.area.
      </p>
      <footer className="panel-foot">
        <button
          type="button"
          className="danger"
          disabled={readOnly || busy}
          title={readOnly ? "Main je pouze pro čtení." : "Zobrazí dopad před smazáním"}
          onClick={onDelete}
        >
          Smazat oblast
        </button>
      </footer>
    </div>
  );
}
