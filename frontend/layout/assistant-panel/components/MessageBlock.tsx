import { useMemo } from "react";
import type { ChatItem } from "../logic/assistant-events";
import { parseDecisions } from "../logic/decisions";
import DecisionCards from "./DecisionCards";
import Markdown from "./Markdown";

type Message = Extract<ChatItem, { kind: "message" }>;

/**
 * Jedna zpráva konverzace bez bublin. Uživatel je odsazený blok s akcentní linkou vlevo a textem tak,
 * jak ho napsal; asistent je čistý text přes celý sloupec vykreslený jako Markdown. Odpověď s aspoň
 * dvěma otázkami ve tvaru grillingu dostane místo souvislého textu karty otázek.
 */
export default function MessageBlock({ message }: { message: Message }) {
  const decisions = useMemo(() => (message.role === "assistant" ? parseDecisions(message.text) : null), [message.role, message.text]);
  if (message.role === "user") {
    return (
      <div className="assistant-panel__message assistant-panel__message--user">
        <span className="assistant-panel__message-who">Vy</span>
        <div className="assistant-panel__message-text">{message.text}</div>
      </div>
    );
  }
  return (
    <div className={"assistant-panel__message assistant-panel__message--assistant" + (message.streaming ? " assistant-panel__message--streaming" : "")}>
      {decisions ? <DecisionCards messageId={message.id} set={decisions} /> : <Markdown text={message.text} />}
    </div>
  );
}
