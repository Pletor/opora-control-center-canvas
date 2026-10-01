// Blok Pravidla: co pro uzel platí (musí / nesmí). Koncept nového pravidla drží lokálně, uložení bublá nahoru.
import { useState } from "react";
import type { NodeRule, RuleKind } from "@/shared/desktop-state/logic/types";

export default function RulesBlock({
  rules,
  disabled,
  readOnly,
  onMove,
  onRemove,
  onAdd,
}: {
  rules: NodeRule[];
  disabled: boolean;
  readOnly: boolean;
  onMove: (index: number, delta: number) => void;
  onRemove: (id: string) => void;
  onAdd: (text: string, kind: RuleKind) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState<RuleKind>("must");
  function submit() {
    const value = text.trim();
    if (!value) return;
    onAdd(value, kind).then((ok) => {
      if (ok) setText("");
    });
  }
  return (
    <>
      <ol>
        {rules.map((rule, index) => (
          <li key={rule.id}>
            <span className={`rule-kind ${rule.kind}`}>{rule.kind === "must" ? "MUSÍ" : "NESMÍ"}</span>
            <span className="block-label">{rule.text}</span>
            <span className="block-tools">
              <button type="button" aria-label="Posunout výš" disabled={disabled || index === 0} onClick={() => onMove(index, -1)}>▲</button>
              <button type="button" aria-label="Odebrat pravidlo" disabled={disabled} onClick={() => onRemove(rule.id)}>✕</button>
            </span>
          </li>
        ))}
      </ol>
      <div className="block-form">
        <input
          aria-label="Nové pravidlo uzlu"
          placeholder="Např. heslo se nikdy neloguje"
          value={text}
          disabled={readOnly}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
        />
        <select aria-label="Druh pravidla" value={kind} disabled={readOnly} onChange={(e) => setKind(e.target.value as RuleKind)}>
          <option value="must">musí</option>
          <option value="must_not">nesmí</option>
        </select>
      </div>
      <button type="button" className="block-add" disabled={disabled || !text.trim()} onClick={submit}>
        + Pravidlo
      </button>
    </>
  );
}
