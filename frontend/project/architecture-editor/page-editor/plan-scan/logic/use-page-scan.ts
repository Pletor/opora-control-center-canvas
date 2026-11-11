// Běh skenu jedné stránky: spuštění, dotaz na stav každé 3 s sdíleným pollerem (`usePolling`, dotazy se nepřekrývají),
// strop 10 minut, Zrušit a Zahodit. Zrušit jen přestane čekat (kontrakt nemá endpoint pro zastavení; server sken
// dokončí nebo ukončí sám). Zahodit hotový návrh zahodí i na serveru. Po otevření stránky se obnoví poslední hotový
// a nepřevzatý sken (`scan/latest`), aby se návrh odchodem ze stránky neztratil. Změna stránky běh zahodí.
import { useEffect, useState } from "react";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { discardScan, readLatestScan, readScan, startScan, type ScanProposal } from "./page-scan";

export const SCAN_POLL_MS = 3000;
export const SCAN_LIMIT_MS = 10 * 60 * 1000;

export type PageScan =
  | { phase: "idle" }
  | { phase: "starting" }
  | { phase: "running"; scanId: string; since: number; elapsed: number }
  | { phase: "done"; scanId: string; proposal: ScanProposal; cost: number | null }
  | { phase: "failed"; error: string };

const message = (cause: unknown) => (cause instanceof Error ? cause.message : String(cause));

export function usePageScan(project: string, workspace: string, pageId: string | null) {
  const [scan, setScan] = useState<PageScan>({ phase: "idle" });
  const [discardError, setDiscardError] = useState("");
  useEffect(() => {
    setScan({ phase: "idle" }); setDiscardError("");
    if (!pageId) return;
    let alive = true;
    // Obnova je tichá: chybějící návrh i nedostupná routa = nic; nepřepíše sken, který mezitím člověk spustil.
    readLatestScan({ project, workspace }, pageId).then((latest) => {
      if (!alive || !latest || latest.state.state !== "done") return;
      const { proposal, cost } = latest.state;
      setScan((current) => (current.phase === "idle" ? { phase: "done", scanId: latest.scanId, proposal, cost } : current));
    }, () => undefined);
    return () => { alive = false; };
  }, [project, workspace, pageId]);
  const scanId = scan.phase === "running" ? scan.scanId : null;
  // Výsledek patří jen skenu, pro který dotaz běžel; mezitím zrušený nebo nahrazený sken se nepřepíše.
  const settle = (id: string, next: (current: Extract<PageScan, { phase: "running" }>) => PageScan) =>
    setScan((current) => (current.phase === "running" && current.scanId === id ? next(current) : current));
  usePolling(async () => {
    if (!scanId) return;
    try {
      const result = await readScan({ project, workspace }, scanId);
      settle(scanId, (current) => {
        const elapsed = Date.now() - current.since;
        if (result.state === "done") return { phase: "done", scanId: current.scanId, proposal: result.proposal, cost: result.cost };
        if (result.state === "failed") return { phase: "failed", error: result.error };
        return elapsed > SCAN_LIMIT_MS ? { phase: "failed", error: "Sken trval déle než 10 minut. Zkuste to znovu nebo s jinou adresou." } : { ...current, elapsed };
      });
    } catch (cause) { settle(scanId, () => ({ phase: "failed", error: message(cause) })); }
  }, { intervalMs: SCAN_POLL_MS, enabled: !!scanId, immediate: false });
  async function start(url: string, note: string) {
    if (!pageId) return;
    setScan({ phase: "starting" }); setDiscardError("");
    try { setScan({ phase: "running", scanId: await startScan({ project, workspace }, pageId, url, note), since: Date.now(), elapsed: 0 }); }
    catch (cause) { setScan({ phase: "failed", error: message(cause) }); }
  }
  /** Zahodit hotový návrh: server ho označí a obnova ho už neukáže; selhání nechá panel otevřený s důvodem. */
  async function discard() {
    if (scan.phase !== "done") return setScan({ phase: "idle" });
    setDiscardError("");
    try { await discardScan({ project, workspace }, scan.scanId); setScan({ phase: "idle" }); }
    catch (cause) { setDiscardError(`Návrh se nepodařilo zahodit: ${message(cause)}`); }
  }
  return { scan, start, discard, discardError, reset: () => { setScan({ phase: "idle" }); setDiscardError(""); } };
}
