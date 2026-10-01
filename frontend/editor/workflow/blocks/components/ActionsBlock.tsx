// Blok Akce: pipeline z knihovny v pořadí výrobní linky. Výběr pipeline deleguje na rodiče (pop-up).
import type { NodeAction } from "@/shared/desktop-state/logic/types";

export default function ActionsBlock({
  actions,
  disabled,
  onMove,
  onRemove,
  onAdd,
}: {
  actions: NodeAction[];
  disabled: boolean;
  onMove: (index: number, delta: number) => void;
  onRemove: (id: string) => void;
  onAdd: () => void;
}) {
  return (
    <>
      <ol>
        {actions.map((action, index) => (
          <li key={action.id}>
            <span className="block-index">#{index + 1}</span>
            <span className="block-label">
              {action.label}
              <small>{action.pipelineId}</small>
            </span>
            <span className="block-tools">
              <button type="button" aria-label="Posunout výš" disabled={disabled || index === 0} onClick={() => onMove(index, -1)}>▲</button>
              <button type="button" aria-label="Posunout níž" disabled={disabled || index === actions.length - 1} onClick={() => onMove(index, 1)}>▼</button>
              <button type="button" aria-label="Odebrat akci" disabled={disabled} onClick={() => onRemove(action.id)}>✕</button>
            </span>
          </li>
        ))}
      </ol>
      <button type="button" className="block-add" disabled={disabled} onClick={onAdd}>
        + Akce
      </button>
    </>
  );
}
