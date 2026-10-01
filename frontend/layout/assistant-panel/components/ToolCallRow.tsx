import type { ChatItem } from "../logic/assistant-events";

type Tool = Extract<ChatItem, { kind: "tool" }>;

const MARK = { running: "…", ok: "✓", error: "✕" } as const;
const LABEL = { running: "běží", ok: "v pořádku", error: "chyba" } as const;

/** Sbalený řádek volání nástroje: název, souhrn a ikona výsledku. Výsledek se otevře klikem. */
export default function ToolCallRow({ tool }: { tool: Tool }) {
  return (
    <details className={`assistant-panel__tool assistant-panel__tool--${tool.status}`}>
      <summary className="assistant-panel__tool-line">
        <span className="assistant-panel__tool-mark" role="img" aria-label={LABEL[tool.status]}>{MARK[tool.status]}</span>
        <span className="assistant-panel__tool-name">{tool.name}</span>
        <span className="assistant-panel__tool-summary">{tool.summary}</span>
      </summary>
      {tool.result && <pre className="assistant-panel__tool-result">{tool.result}</pre>}
    </details>
  );
}
