import { useState, type ReactNode } from "react";
import "../styles/node-detail.css";

/** Load a secondary editor on first opening; keep its draft mounted when folded again. */
export default function DetailFold({ title, children }: { title: string; children: ReactNode }) {
  const [visited, setVisited] = useState(false);
  return <details className="node-detail-fold" onToggle={(event) => { if (event.currentTarget.open) setVisited(true); }}>
    <summary>{title}</summary>
    {visited && <div className="node-detail-fold__body">{children}</div>}
  </details>;
}
