import { useMemo } from "react";
import type { ChatItem } from "../logic/assistant-events";
import { parseDecisions } from "../logic/decisions";
import { pastePreview, splitMessage } from "../logic/pasted-blocks";
import DecisionCards from "./DecisionCards";
import Markdown from "./Markdown";

type Message = Extract<ChatItem, { kind: "message" }>;

/**
 * Jedna zpráva konverzace bez bublin. Uživatel je odsazený blok s akcentní linkou vlevo a textem tak,
 * jak ho napsal a vložené dlouhé texty jako sbalené dlaždice (rozbalí se kliknutím); asistent je čistý text přes celý sloupec vykreslený jako Markdown. Odpověď s aspoň
 * dvěma otázkami ve tvaru grillingu dostane místo souvislého textu karty otázek.
 */
export default function MessageBlock({ message }: { message: Message }) {
  const decisions = useMemo(() => (message.role === "assistant" ? parseDecisions(message.text) : null), [message.role, message.text]);
  const user = useMemo(() => (message.role === "user" ? splitMessage(message.text) : null), [message.role, message.text]);
  if (user) {
    return (
      <div className="assistant-panel__message assistant-panel__message--user">
        <span className="assistant-panel__message-who">Vy</span>
        {user.text && <div className="assistant-panel__message-text">{user.text}</div>}
        {user.blocks.map((text, i) => (
          <details key={i} className="assistant-panel__message-paste">
            <summary className="assistant-panel__message-paste-head">
              <span className="assistant-panel__pasted-badge">Vloženo</span>
              <span className="assistant-panel__message-paste-preview">{pastePreview(text)}</span>
            </summary>
            <div className="assistant-panel__message-text">{text}</div>
          </details>
        ))}
      </div>
    );
  }
  return (
    <div className={"assistant-panel__message assistant-panel__message--assistant" + (message.streaming ? " assistant-panel__message--streaming" : "")}>
      {decisions ? <DecisionCards messageId={message.id} set={decisions} /> : <Markdown text={message.text} />}
    </div>
  );
}
