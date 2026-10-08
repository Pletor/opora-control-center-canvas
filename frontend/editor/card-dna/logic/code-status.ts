import type { SyncReport, SyncSignal, SyncVerdict } from "@/shared/desktop-state/logic/types";

export type AssignmentStatusKind = "current" | "changed" | "unbound" | "unavailable";
export type AssignmentStatusView = { kind: AssignmentStatusKind; explanation: string };
export type SyncStatusKind = "synced" | "app-ahead" | "repo-ahead" | "unknown" | "missing" | "mixed" | "unsupported";
export type SyncStatusView = { kind: SyncStatusKind; explanation: string; signals: SyncSignal[]; verdict: SyncVerdict | null };

/** Odkaz na commit vznikne jen z ověřitelné identity repozitáře v GitHub PR a hex SHA, nikdy z dodané URL přímo. */
export function githubCommitUrl(prUrl: string | undefined, commit: string | undefined): string | null {
  if (!prUrl || !commit || !/^[0-9a-f]{7,64}$/i.test(commit)) return null;
  try {
    const url = new URL(prUrl);
    const match = url.protocol === "https:" && url.hostname.toLowerCase() === "github.com" && !url.username && !url.password
      ? url.pathname.match(/^\/([^/]+)\/([^/]+)\/pull\/\d+\/?$/) : null;
    return match ? `https://github.com/${match[1]}/${match[2]}/commit/${commit}` : null;
  } catch { return null; }
}

export function assignmentStatusView(status: "current" | "changed" | "unbound" | undefined): AssignmentStatusView {
  switch (status) {
    case "current": return { kind: status, explanation: "Zadání odpovídá snímku přiřazenému k výstupu." };
    case "changed": return { kind: status, explanation: "Zadání se od snímku přiřazeného k výstupu změnilo." };
    case "unbound": return { kind: status, explanation: "Výstup nemá přiřazený snímek zadání." };
    default: return { kind: "unavailable", explanation: "Stav přiřazení zadání zatím není k dispozici; nelze tvrdit, že je beze změny." };
  }
}

/** Jen `spec-ahead` má u konkrétního uzlu doložený směr mezi zadáním a kódem; ostatní echo není směr synchronizace. */
export function syncStatusView(report: SyncReport | null, nodeId: string): SyncStatusView {
  if (!report) return { kind: "missing", explanation: "Report OporaHubu pro kartu není k dispozici.", signals: [], verdict: null };
  const verdict = report.verdicts.find(item => item.scope.kind === "node" && item.scope.id === nodeId) ?? null;
  const signals = report.signals.filter(item => item.subject.scope === "node" && item.subject.id === nodeId);
  const signalKinds = new Set(signals.map(item => item.type));
  const hasAppAhead = signalKinds.has("spec-ahead");
  const unsupported = [...signalKinds].some(type => type !== "spec-ahead");
  if (verdict?.state === "green" && signals.length) return { kind: "mixed", explanation: "Zelený verdikt a echo k této kartě si odporují; stav nelze zjednodušit.", signals, verdict };
  if (hasAppAhead && unsupported) return { kind: "mixed", explanation: "Echo obsahuje známý rozdíl zadání i další nepodporované signály; stav nelze zjednodušit.", signals, verdict };
  if (hasAppAhead) return { kind: "app-ahead", explanation: "Zadání má doloženou novější revizi než poslední pár kódu.", signals, verdict };
  if (unsupported) return { kind: "unsupported", explanation: "Report obsahuje echo pro kartu, ale jeho typ neurčuje směr synchronizace.", signals, verdict };
  if (verdict?.state === "green") return { kind: "synced", explanation: "Zelený verdikt pro tuto kartu potvrzuje soulad zadání, kódu, testů a důkazů.", signals, verdict };
  if (verdict) return { kind: "unknown", explanation: `Verdikt „${verdict.state}“ neurčuje směr synchronizace kódu.`, signals, verdict };
  return { kind: "missing", explanation: "Report neobsahuje verdikt ani echo pro tuto kartu; stav synchronizace nelze určit.", signals, verdict };
}
