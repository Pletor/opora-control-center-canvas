import { useState } from "react";
import { useLeaseClock } from "@/editor/card-dna/logic/lease-clock";
import type { CardLease as Lease } from "../logic/use-leases";

export function leaseSeconds(lease: Lease, now: number) {
  return Math.max(0, Math.ceil(lease.expiresAt - now / 1000 - lease.serverOffset));
}
/** Detail lease sdílí ticker s kompaktní kartou; uvolnění zůstává dostupné jen při předaném callbacku. */
export default function CardLease({ lease, release }: { lease: Lease; release?: () => Promise<unknown> }) {
  const now = useLeaseClock();
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState("");
  const remaining = leaseSeconds(lease, now);
  async function free() {
    if (!release || state !== "idle") return;
    setState("busy"); setError("");
    try { await release(); setState("done"); }
    catch (error) { setError(error instanceof Error ? error.message : String(error)); setState("idle"); }
  }
  return <div className="nodrag nopan" style={{ padding: "6px 12px", color: remaining && state !== "done" ? "#2563eb" : "#94a3b8" }}>
    🤖 {lease.owner} · {state === "done" ? "uvolněno" : remaining ? `převzato ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}` : "převzetí vypršelo"}
    {release && state !== "done" && <button type="button" style={{ marginLeft: 8 }} disabled={state === "busy"} title="Uvolnit převzetí karty agentem (člověk smí bez tokenu)" onClick={event => { event.stopPropagation(); void free(); }}>{state === "busy" ? "Uvolňuji…" : "Uvolnit"}</button>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
