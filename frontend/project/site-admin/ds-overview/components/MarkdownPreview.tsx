import { createElement } from "react";
import { parseMarkdown, type Inline } from "../logic/markdown";

function InlineText({ parts }: { parts: Inline[] }) {
  return <>{parts.map((part, index) => part.kind === "code" ? <code key={index} className="ds-overview__md-code">{part.text}</code>
    : part.kind === "strong" ? <strong key={index}>{part.text}</strong>
    : part.kind === "em" ? <em key={index}>{part.text}</em>
    : part.kind === "link" ? <a key={index} className="ds-overview__md-link" href={part.href} target="_blank" rel="noreferrer noopener">{part.text}</a>
    : <span key={index}>{part.text}</span>)}</>;
}

/** Náhled brand booku složený z React prvků (žádné vkládání HTML). */
export default function MarkdownPreview({ source }: { source: string }) {
  const blocks = parseMarkdown(source);
  if (!blocks.length) return <p className="ds-overview__md-empty">README je prázdné. Napiš, jak web mluví, co dělat a co ne a jak systém používat.</p>;
  return <div className="ds-overview__md">{blocks.map((block, index) => {
    if (block.kind === "heading") return createElement("h" + Math.min(block.level + 1, 6), { key: index, className: "ds-overview__md-h ds-overview__md-h--" + block.level }, <InlineText parts={block.inline}/>);
    if (block.kind === "paragraph") return <p key={index} className="ds-overview__md-p"><InlineText parts={block.inline}/></p>;
    if (block.kind === "quote") return <blockquote key={index} className="ds-overview__md-quote"><InlineText parts={block.inline}/></blockquote>;
    if (block.kind === "code") return <pre key={index} className="ds-overview__md-pre">{block.text}</pre>;
    if (block.kind === "rule") return <hr key={index} className="ds-overview__md-rule"/>;
    const items = block.items.map((item, at) => <li key={at} className="ds-overview__md-li"><InlineText parts={item}/></li>);
    return block.ordered ? <ol key={index} className="ds-overview__md-list">{items}</ol> : <ul key={index} className="ds-overview__md-list">{items}</ul>;
  })}</div>;
}
