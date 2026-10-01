// Stav bloku: status, podmínka a dvě větve (splněno → / nesplněno →). Cíl větve je vždy existující ID.
import { BLOCK_STATUSES, type BlockState as BlockStateValue, type BlockStatus, type Branch } from "@/shared/desktop-state/logic/types";
import { branchLabel, type BranchTarget } from "@/editor/node-detail/tree/logic/tree-model";

const STATUS_LABEL: Record<BlockStatus, string> = { open: "otevřeno", met: "splněno", unmet: "nesplněno", blocked: "blokováno" };

function BranchPicker({ via, value, targets, disabled, onChange }: {
  via: "onMet" | "onUnmet";
  value: Branch;
  targets: BranchTarget[];
  disabled: boolean;
  onChange: (branch: Branch) => void;
}) {
  const key = value.kind === "none" ? "none" : `${value.kind}:${value.targetId}`;
  return (
    <div className={`tree-branch tree-branch-${via}`}>
      <span className="tree-branch-when">{via === "onMet" ? "Splněno →" : "Nesplněno →"}</span>
      <select aria-label={via === "onMet" ? "Co dál při splnění" : "Co dál při nesplnění"} value={key} disabled={disabled}
        onChange={(e) => {
          const [kind, ...rest] = e.target.value.split(":");
          onChange(kind === "none" ? { kind: "none", targetId: "", note: value.note } : { kind: kind as Branch["kind"], targetId: rest.join(":"), note: value.note });
        }}>
        <option value="none">nic dalšího</option>
        {targets.map((t) => <option key={`${t.kind}:${t.id}`} value={`${t.kind}:${t.id}`}>{t.kind === "block" ? "blok" : t.kind === "node" ? "uzel" : "akce"} · {t.label}</option>)}
      </select>
      <input aria-label="Poznámka k větvi" placeholder="poznámka" value={value.note} disabled={disabled}
        onChange={(e) => onChange({ ...value, note: e.target.value })} />
      <small className="tree-branch-label">{branchLabel(value, targets)}</small>
    </div>
  );
}

export default function BlockState({
  state,
  targets,
  disabled,
  onStatus,
  onCondition,
  onBranch,
}: {
  state: BlockStateValue;
  targets: BranchTarget[];
  disabled: boolean;
  onStatus: (status: BlockStatus) => void;
  onCondition: (condition: string) => void;
  onBranch: (via: "onMet" | "onUnmet", branch: Branch) => void;
}) {
  return (
    <section className="tree-part tree-state" aria-label="Stav bloku">
      <h5>Stav</h5>
      <div className="tree-status" role="radiogroup" aria-label="Status bloku">
        {BLOCK_STATUSES.map((status) => (
          <button key={status} type="button" role="radio" aria-checked={state.status === status} className={`tree-status-${status}`} disabled={disabled}
            onClick={() => onStatus(status)}>
            {STATUS_LABEL[status]}
          </button>
        ))}
      </div>
      <label className="tree-condition">
        Podmínka splnění
        <input value={state.condition} disabled={disabled} placeholder="Např. testy přihlášení zelené" onChange={(e) => onCondition(e.target.value)} />
      </label>
      <BranchPicker via="onMet" value={state.onMet} targets={targets} disabled={disabled} onChange={(b) => onBranch("onMet", b)} />
      <BranchPicker via="onUnmet" value={state.onUnmet} targets={targets} disabled={disabled} onChange={(b) => onBranch("onUnmet", b)} />
    </section>
  );
}
