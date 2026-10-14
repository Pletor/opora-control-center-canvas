import { useEffect, useState } from "react";
import type { CardLease as Lease } from "../logic/use-leases";
export function leaseSeconds(lease: Lease, now: number) {
  return Math.max(0, Math.ceil(lease.expiresAt - now / 1000 - lease.serverOffset));
}
export default function CardLease({ lease, release }: { lease: Lease; release?: () => Promise<unknown> }) {
  const [now, setNow] = useState(Date.now());
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState("");
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const remaining = leaseSeconds(lease, now);
  async function free() {
    if (!release || state !== "idle") return;
    setState("busy"); setError("");
    try { await release(); setState("done"); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); setState("idle"); }
  }
  return <div className={"nodrag nopan node-card__row " + (remaining && state !== "done" ? "node-card__row--live" : "node-card__row--muted")}>
    🤖 {lease.owner} · {state === "done" ? "uvolněno" : remaining ? `převzato ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}` : "převzetí vypršelo"}
    {release && state !== "done" && <button type="button" disabled={state === "busy"}
      title="Uvolnit převzetí karty agentem (člověk smí bez tokenu)"
      onClick={event => { event.stopPropagation(); void free(); }}>{state === "busy" ? "Uvolňuji…" : "Uvolnit"}</button>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
