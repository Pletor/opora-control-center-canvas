import { useState } from "react";
import { specFacts, type LensRecord } from "../logic/lens-read";

function when(stamp: string) {
  const date = new Date(stamp);
  return Number.isNaN(date.getTime()) ? stamp : date.toLocaleString("cs-CZ", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Hlavička: PR a hlava (nebo mapa oblasti z plánu), kdy byl spec ověřen, jeho velikost a kopie pro agenta. */
export default function LensHeader({ record, hasArea }: { record: LensRecord; hasArea: boolean }) {
  const [copied, setCopied] = useState<"" | "ok" | "fail">("");
  function copy() {
    const text = JSON.stringify(record.spec, null, 2);
    (navigator.clipboard?.writeText(text) ?? Promise.reject(new Error("clipboard")))
      .then(() => setCopied("ok"), () => setCopied("fail"))
      .finally(() => window.setTimeout(() => setCopied(""), 2000));
  }
  const pr = record.kind === "pr";
  return <header className="review-lens__head" data-oh-lens-pr={record.prNumber ?? ""} data-oh-lens-current={String(record.current ?? "")}>
    <div className="review-lens__head-line">
      {pr ? <code className="review-lens__pr">PR #{record.prNumber}</code> : <span className="review-lens__chip review-lens__chip--plan">plán</span>}
      {pr ? <code className="review-lens__sha" title={record.headSha ?? ""}>{record.headSha?.slice(0, 12)}</code>
        : <span className="review-lens__muted">mapa oblasti · revize plánu <code>{record.acceptedRevision?.slice(0, 12)}</code></span>}
      {pr && record.current !== null && <span className={`review-lens__chip review-lens__chip--${record.current ? "ok" : "warn"}`}
        data-oh-lens-fresh={record.current ? "current" : "stale"}>{record.current ? "✓ aktuální hlava" : "◷ starší hlava"}</span>}
      {pr && hasArea && <span className="review-lens__muted">nahradil mapu z plánu</span>}
      <span className="review-lens__grow" />
      <button type="button" className="review-lens__copy" data-oh-lens-copy="" onClick={copy}>
        {copied === "ok" ? "✓ Zkopírováno" : copied === "fail" ? "Kopírování selhalo" : "Kopírovat spec pro agenta"}</button>
    </div>
    <div className="review-lens__head-line review-lens__muted">
      <span>ověřeno {when(record.validatedAt)}</span><span aria-hidden="true">·</span>
      <span data-oh-lens-facts="">{specFacts(record.spec)}</span>
      {record.by && <><span aria-hidden="true">·</span><span>{record.by}</span></>}
    </div>
  </header>;
}
