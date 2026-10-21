import { useEffect, useState } from "react";

/** Přesný dokument agent-state ke zkopírování; stejný text jako zrcadlo script#oh-agent-state. */
export default function StateJson({ endpoint, json }: { endpoint: string; json: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => { if (!copied) return; const timer = setTimeout(() => setCopied(false), 1500); return () => clearTimeout(timer); }, [copied]);
  function copy() {
    void navigator.clipboard?.writeText(json).then(() => setCopied(true), () => setCopied(false));
  }
  return <section className="oporahub-agents__panel" data-oh-block="state-json">
    <header className="oporahub-agents__panel-head"><h2 className="oporahub-agents__title oporahub-agents__title--mono">GET {endpoint}</h2>
      <button type="button" className="oporahub-agents__copy" onClick={copy}>{copied ? "zkopírováno ✓" : "kopírovat JSON"}</button></header>
    <pre className="oporahub-agents__code">{json}</pre>
  </section>;
}
