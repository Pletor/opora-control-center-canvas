import { useState } from "react";
import NodeSpecEditor from "./NodeSpecEditor";
import type { CanvasNode, Workspace } from "./types";
export default function NodePanel({
  node,
  project,
  workspace,
  readOnly,
  busy,
  workspaces,
  onEnter,
  onSave,
  onWorkspace,
  onDelete,
}: {
  node: CanvasNode;
  project: string;
  workspace: string;
  readOnly: boolean;
  busy: boolean;
  workspaces: Workspace[];
  onEnter: () => void;
  onSave: (n: CanvasNode) => void;
  onWorkspace: () => void;
  onDelete: () => void;
}) {
  const [purpose, setPurpose] = useState(node.purpose);
  const [confirmed, setConfirmed] = useState(false);
  const assigned = workspaces.filter((w) => w.node_id === node.id);
  return (
    <aside className="detail">
      <div className="eyebrow">
        {node.kind === "sector" ? "SEKTOR" : "UZEL"} · DETAIL
      </div>
      <h2>{node.name}</h2>
      <code className="identity">{node.id}</code>
      <button className="wide" onClick={onEnter}>
        Otevřít vnitřní plátno
      </button>
      <button className="danger wide" disabled={readOnly || busy} title={readOnly ? "Main je pouze pro čtení. Přepněte do pracovního prostoru." : "Zobrazit dopad před smazáním"} onClick={onDelete}>
        {node.kind === "sector" ? "Smazat sektor" : "Smazat uzel"}
      </button>
      <NodeSpecEditor project={project} workspace={workspace} nodeId={node.id} disabled={busy} />
      <h3>Podstata</h3>
      <label className="field">
        Proč tento uzel existuje
        <textarea
          aria-label="Podstata uzlu"
          rows={7}
          maxLength={12000}
          value={purpose}
          readOnly={readOnly}
          onChange={(e) => {
            setPurpose(e.target.value);
            setConfirmed(false);
          }}
        />
      </label>
      {!readOnly && purpose !== node.purpose && (
        <>
          <label className="check">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            Potvrzuji změnu podstaty.
          </label>
          <button
            disabled={busy || !confirmed}
            onClick={() => onSave({ ...node, purpose })}
          >
            Uložit podstatu
          </button>
        </>
      )}
      <h3>Pracovní prostory uzlu</h3>
      {assigned.length ? (
        assigned.map((w) => (
          <div className="assignment" key={w.id}>
            <strong>{w.actor}</strong>
            <code>{w.branch}</code>
            <p>Přiřazený vlastník, aktivita agenta není ověřena.</p>
          </div>
        ))
      ) : (
        <p className="muted">Žádný doložený pracovní prostor tohoto uzlu.</p>
      )}
      <button onClick={onWorkspace}>Připravit oddělený worktree</button>
      <div className="boundary-note">
        Hotovo není barva karty. Dokončení musí být doloženo testy, review a
        merge do schválené větve.
      </div>
    </aside>
  );
}
