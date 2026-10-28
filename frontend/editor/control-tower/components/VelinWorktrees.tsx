// Práce ve worktree ve Velínu: řádek na worktree „větev · aktér · zavírá N děr · otevírá M nových“; rozbalení vypíše
// nové díry jantarově a klik na díru s kartou otevře její detail stejně jako ostatní položky Velínu. Bez worktree nic.
import { worktreeWorkLine, type VelinWorktreeRow } from "../logic/velin-worktrees";

export default function VelinWorktrees({ rows, onOpen }: { rows: VelinWorktreeRow[]; onOpen: (nodeId: string) => void }) {
  if (!rows.length) return null;
  return (
    <section className="velin__worktrees" aria-label="Práce ve worktree" data-oh-worktrees={rows.length}>
      <b className="velin__worktrees-title">Práce ve worktree</b>
      <ul className="velin__worktree-list">
        {rows.map(row => (
          <li key={row.workspaceId} data-oh-workspace={row.workspaceId} data-oh-closed={row.closed} data-oh-opened={row.opened.length}>
            <details className={"velin__worktree" + (row.opened.length ? " velin__worktree--opens" : "")}>
              <summary className="velin__worktree-head">
                <span className="velin__worktree-glyph" aria-hidden="true">⑂</span>
                <code className="velin__worktree-branch" title={row.branch}>{row.branch}</code>
                {row.actor && <span className="velin__worktree-actor">{row.actor}</span>}
                <span className="velin__worktree-line">{worktreeWorkLine(row)}</span>
              </summary>
              {!row.opened.length && <p className="velin__worktree-none">Práce zatím neotevírá žádnou novou díru.</p>}
              {row.opened.length > 0 && <ul className="velin__worktree-holes" aria-label={`Nové díry ve ${row.branch}`}>
                {row.opened.map(hole => (
                  <li key={hole.key}>
                    <button type="button" className="velin__worktree-hole" disabled={!hole.nodeId} onClick={() => hole.nodeId && onOpen(hole.nodeId)}
                      title={hole.ruleLabel} data-oh-hole-key={hole.key} data-oh-node-id={hole.nodeId ?? ""}>
                      <span className="velin__worktree-hole-glyph" aria-hidden="true">＋</span>
                      <span className="velin__worktree-hole-text">nová díra: {hole.message}</span>
                      <small className="velin__worktree-hole-card">{hole.cardName}</small>
                    </button>
                  </li>
                ))}
              </ul>}
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}
