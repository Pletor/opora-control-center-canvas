import { useMemo, type ReactNode } from "react";
import { parseMarkdown, type Block, type Inline } from "../logic/markdown";

/**
 * Odpověď asistenta jako dokument: struktura z `logic/markdown.ts` → React prvky. Žádné HTML ani
 * `innerHTML`; všechno je text v prvcích, které skládá React. Odkaz zůstává textem s adresou.
 */
function inline(nodes: Inline[], key = ""): ReactNode[] {
  return nodes.map((node, i) => {
    const k = `${key}${i}`;
    switch (node.type) {
      case "text":
        return node.text;
      case "break":
        return <br key={k} />;
      case "strong":
        return <strong key={k} className="assistant-panel__md-strong">{inline(node.children, k)}</strong>;
      case "em":
        return <em key={k} className="assistant-panel__md-em">{inline(node.children, k)}</em>;
      case "code":
        return <code key={k} className="assistant-panel__md-code">{node.text}</code>;
      case "link":
        return (
          <span key={k} className="assistant-panel__md-link" title={node.href}>
            {node.text} <span className="assistant-panel__md-href">({node.href})</span>
          </span>
        );
    }
  });
}

function block(node: Block, i: number): ReactNode {
  switch (node.type) {
    case "heading": {
      const Tag = (["h3", "h4", "h5", "h5"] as const)[node.level - 1];
      return <Tag key={i} className={`assistant-panel__md-heading assistant-panel__md-heading--${node.level}`}>{inline(node.children)}</Tag>;
    }
    case "paragraph":
      return <p key={i} className="assistant-panel__md-paragraph">{inline(node.children)}</p>;
    case "code":
      return (
        <pre key={i} className="assistant-panel__md-pre" data-lang={node.lang || undefined}>
          <code>{node.text}</code>
        </pre>
      );
    case "list": {
      const items = node.items.map((item, j) => (
        <li key={j} className={"assistant-panel__md-item" + (item.depth ? " assistant-panel__md-item--nested" : "")}>{inline(item.children)}</li>
      ));
      return node.ordered ? (
        <ol key={i} className="assistant-panel__md-list assistant-panel__md-list--ordered" start={node.start}>{items}</ol>
      ) : (
        <ul key={i} className="assistant-panel__md-list">{items}</ul>
      );
    }
    case "quote":
      return <blockquote key={i} className="assistant-panel__md-quote">{inline(node.children)}</blockquote>;
    case "rule":
      return <hr key={i} className="assistant-panel__md-rule" />;
  }
}

export default function Markdown({ text }: { text: string }) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  return <div className="assistant-panel__md">{blocks.map(block)}</div>;
}
