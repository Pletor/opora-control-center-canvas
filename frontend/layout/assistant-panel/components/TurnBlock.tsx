import { turnMeta, type Turn } from "../logic/turns";
import ApprovalCard, { type ApprovalDecision } from "./ApprovalCard";
import MessageBlock from "./MessageBlock";
import ToolSteps from "./ToolSteps";

/**
 * Jeden tah konverzace: tichá hlavička „Tah 2 · 14:06 · 38 s · 6 kroků“, pod ní zpráva uživatele,
 * kroky nástrojů, žádosti o zápis (karta schválení) a odpověď. Hlavička ukazuje jen známé údaje (stav běhu je jednou, na konci konverzace).
 * Sekce nese kotvu, na kterou posouvá osnova, a `data-turn` pro sledování, který tah se právě čte.
 */
export default function TurnBlock({ turn, onDecide }: { turn: Turn; onDecide: ApprovalDecision }) {
  const meta = turnMeta(turn);
  return (
    <section id={turn.anchor} data-turn={turn.anchor} className="assistant-panel__turn" aria-label={`Tah ${turn.index}`}>
      <header className="assistant-panel__turn-head">
        <span className="assistant-panel__turn-number">Tah {turn.index}</span>
        {meta.length > 0 && <span className="assistant-panel__turn-meta">{meta.join(" · ")}</span>}
      </header>
      {turn.user && <MessageBlock message={turn.user} />}
      {turn.entries.map((entry) => {
        if (entry.kind === "steps") return <ToolSteps key={entry.id} tools={entry.tools} />;
        if (entry.kind === "approval") return <ApprovalCard key={entry.item.id} approval={entry.item.approval} onDecide={onDecide} />;
        if (entry.kind === "error") return <p key={entry.item.id} role="alert" className="assistant-panel__error">{entry.item.text}</p>;
        return <MessageBlock key={entry.item.id} message={entry.item} />;
      })}
    </section>
  );
}
