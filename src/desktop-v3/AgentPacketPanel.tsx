import { useEffect, useMemo, useRef, useState } from "react";
import {
  ACTIVE_HANDOFF_STATUSES,
  errorMessage,
  exportHandoff,
  fetchHandoff,
  fetchSnapshot,
  prepareSnapshotRun,
  previewPacket,
  snapshotPacket,
  startHandoff,
  stopHandoff,
} from "./api";
import type { HandoffRun, PacketPreviewResponse, PacketSnapshotResponse } from "./types";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function download(name: string, value: string, mime: string) {
  const url = URL.createObjectURL(new Blob([value], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

const STATUS_LABEL: Record<string, string> = {
  prepared: "Připraveno — model neběží",
  starting: "Spouští se",
  running: "Běží",
  stopping: "Zastavuje se",
  verifying: "Ověřuje se výsledek",
  completed: "Dokončeno",
  failed: "Selhalo",
  cancelled: "Zastaveno",
  interrupted: "Přerušeno",
};

export function AgentPacketPanel({
  project,
  workspace,
  nodeId,
  path,
  references,
  note,
  sessionId = "",
}: {
  project: string;
  workspace: string;
  nodeId: string;
  path: string;
  references: string[];
  note: string;
  /** Skutečně vybraný běh, nikoli lokálně generované ID. Prázdné = náhled bez vazby na konkrétní session
   * (Editor/Projekt). Export souboru má vlastní nonce nezávislý na session. */
  sessionId?: string;
}) {
  const exportNonce = useRef(newId()).current;
  const scopeSignature = useMemo(
    () => JSON.stringify({ project, workspace, nodeId, path, sessionId, references, note }),
    [project, workspace, nodeId, path, sessionId, references, note],
  );
  const [preview, setPreview] = useState<PacketPreviewResponse | null>(null);
  const [previewScope, setPreviewScope] = useState("");
  const [snapshot, setSnapshot] = useState<PacketSnapshotResponse | null>(null);
  const [reloadedSnapshot, setReloadedSnapshot] = useState<PacketSnapshotResponse | null>(null);
  const [task, setTask] = useState("");
  const [run, setRun] = useState<HandoffRun | null>(null);
  const [approved, setApproved] = useState(false);
  const [stopRequested, setStopRequested] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current++;
    };
  }, []);

  // Scope can change via props while this component stays mounted (e.g. the user picks a
  // different node/path/session in the same panel, then picks the previous one again). Each
  // change must invalidate any in-flight request tied to the old scope AND drop task/snapshot/run
  // state that belongs to that old scope, so prepare/start/export can never reuse a stale
  // snapshot under a newly selected node — a plain string comparison of previewScope is not
  // enough because it only guards the preview itself, not requests already in flight.
  const scopeRef = useRef(scopeSignature);
  useEffect(() => {
    if (scopeRef.current === scopeSignature) return;
    scopeRef.current = scopeSignature;
    generation.current++;
    setPreview(null);
    setPreviewScope("");
    setSnapshot(null);
    setReloadedSnapshot(null);
    setTask("");
    setRun(null);
    setApproved(false);
    setStopRequested(false);
    setError("");
    // Bumping generation.current makes the stale request's own finally() a no-op (its ticket
    // no longer matches), so busy would otherwise stay true forever with no request left to
    // ever clear it. Reset it here instead — the new scope starts idle, not stuck mid-build.
    setBusy(false);
  }, [scopeSignature]);

  const scopeStale = Boolean(preview) && previewScope !== scopeSignature;

  async function buildPreview() {
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await previewPacket({ project, workspace, nodeId, path, sessionId, references, note });
      if (!mounted.current || ticket !== generation.current) return;
      setPreview(value);
      setPreviewScope(scopeSignature);
      setSnapshot(null);
      setReloadedSnapshot(null);
      // A fresh preview within the SAME scope must not hide an active run's stop control —
      // only clear it once it is no longer active (its outcome is already visible/exported).
      setRun((current) => (current && ACTIVE_HANDOFF_STATUSES.has(current.status) ? current : null));
    } catch (e) {
      if (mounted.current && ticket === generation.current) setError(errorMessage(e));
    } finally {
      if (mounted.current && ticket === generation.current) setBusy(false);
    }
  }

  async function createSnapshot() {
    if (!preview || scopeStale) return;
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await snapshotPacket({
        project,
        workspace,
        nodeId,
        path,
        sessionId,
        references,
        note,
        digest: preview.digest,
      });
      if (!mounted.current || ticket !== generation.current) return;
      setSnapshot(value);
      setReloadedSnapshot(null);
    } catch (e) {
      if (mounted.current && ticket === generation.current) {
        setError(`${errorMessage(e)} — zdroje se mohly změnit od náhledu; vytvořte nový náhled.`);
        setPreview(null);
      }
    } finally {
      if (mounted.current && ticket === generation.current) setBusy(false);
    }
  }

  async function reloadSnapshot() {
    if (!snapshot) return;
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await fetchSnapshot(snapshot.id, project, workspace);
      if (!mounted.current || ticket !== generation.current) return;
      if (value.digest !== snapshot.digest) throw new Error("Načtený snímek neodpovídá vytvořenému digestu.");
      setReloadedSnapshot(value);
    } catch (e) {
      if (mounted.current && ticket === generation.current) setError(errorMessage(e));
    } finally {
      if (mounted.current && ticket === generation.current) setBusy(false);
    }
  }

  const validTask = task.trim().length >= 10 && task.length <= 4000;

  async function perform(action: () => Promise<HandoffRun>) {
    if (busy) return;
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const value = await action();
      if (!mounted.current || ticket !== generation.current) return;
      setRun(value);
      setApproved(false);
      if (value.status === "stopping" || !ACTIVE_HANDOFF_STATUSES.has(value.status)) setStopRequested(false);
    } catch (e) {
      if (mounted.current && ticket === generation.current) setError(errorMessage(e));
    } finally {
      if (mounted.current && ticket === generation.current) setBusy(false);
    }
  }

  useEffect(() => {
    if (!run || !ACTIVE_HANDOFF_STATUSES.has(run.status)) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const runId = run.id;
    const poll = async () => {
      try {
        const value = await fetchHandoff(runId);
        if (value.id !== runId) throw new Error("Cizí odpověď běhu.");
        if (!cancelled) {
          setRun(value);
          if (ACTIVE_HANDOFF_STATUSES.has(value.status)) timer = setTimeout(poll, 1200);
        }
      } catch {
        if (!cancelled) {
          setError("Stav běhu se nepodařilo ověřit. Nejde o potvrzení zastavení.");
          timer = setTimeout(poll, 2500);
        }
      }
    };
    timer = setTimeout(poll, 700);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [run?.id, run?.status]);

  const active = Boolean(run && ACTIVE_HANDOFF_STATUSES.has(run.status));
  const stopPending = run?.status === "stopping" && !run.error;
  const includedCount = preview?.packet.sourceManifest.filter((m) => m.included).length ?? 0;
  const totalCount = preview?.packet.sourceManifest.length ?? 0;

  return (
    <section className="v3-panel v3-agent-packet" aria-label="Podklady pro agenta">
      <header className="v3-panel-head">
        <h2>Podklady pro agenta</h2>
        <p className="v3-note">
          Uzel {nodeId || "nevybrán"} · cesta {path || "—"} · {references.length} referencí
        </p>
      </header>
      {error && <p role="alert" className="v3-error">{error}</p>}

      <section className="v3-section" aria-label="Náhled balíčku">
        <h3>1 · Náhled</h3>
        <button type="button" disabled={busy} onClick={buildPreview}>
          Sestavit náhled balíčku
        </button>
        {scopeStale && (
          <p role="status" className="v3-warn">
            Rozsah výběru se změnil od posledního náhledu. Vytvořte nový náhled před uložením snímku.
          </p>
        )}
        {preview && (
          <>
            <dl className="v3-kv">
              <dt>Digest</dt>
              <dd><code>{preview.digest}</code></dd>
              <dt>Shrnutí</dt>
              <dd>
                {includedCount} / {totalCount} zdrojů zahrnuto
                {preview.packet.warnings.length > 0 && <> · {preview.packet.warnings.length} varování</>}
              </dd>
            </dl>
            <h4>Zdrojový manifest</h4>
            {preview.packet.sourceManifest.length === 0 && <p className="v3-empty">Žádné zdroje.</p>}
            {/* Card list instead of a fixed multi-column table: long UUID owner ids must wrap,
                not force horizontal overflow at narrow inspector widths (320/390px). */}
            <ul className="v3-manifest-list">
              {preview.packet.sourceManifest.map((entry, index) => {
                const labeled = entry as typeof entry & { label?: string; name?: string };
                const humanName = labeled.label || labeled.name || "";
                return (
                  <li key={index} className="v3-manifest-item">
                    <span className="v3-chip">{entry.kind}</span>
                    <span className="v3-manifest-owner" title={entry.ownerId}>
                      {humanName || entry.ownerId}
                    </span>
                    <span className="v3-chip">rev {entry.revision ?? "nedostupné"}</span>
                    <span className={`v3-chip${entry.included ? " v3-chip-ok" : ""}`}>
                      {entry.included ? "zahrnuto" : "nezahrnuto"}
                    </span>
                    <span className="v3-manifest-reason">{entry.reason}</span>
                  </li>
                );
              })}
            </ul>
            {preview.packet.warnings.length > 0 && (
              <ul className="v3-warnings">
                {preview.packet.warnings.map((w, i) => (
                  <li key={i} role="alert">
                    {w}
                  </li>
                ))}
              </ul>
            )}
            <details>
              <summary>Přesný JSON balíček</summary>
              <pre data-testid="packet-json">{JSON.stringify(preview.packet, null, 2)}</pre>
            </details>
            <div className="v3-row">
              <button
                type="button"
                onClick={() =>
                  navigator.clipboard
                    ?.writeText(JSON.stringify(preview.packet, null, 2))
                    .catch(() => setError("Kopírování odmítnuto prohlížečem."))
                }
              >
                Kopírovat
              </button>
              <button
                type="button"
                onClick={() =>
                  download(`opora-packet-${exportNonce}.json`, JSON.stringify(preview.packet, null, 2), "application/json")
                }
              >
                Stáhnout
              </button>
            </div>
          </>
        )}
      </section>

      <section className="v3-section" aria-label="Neměnný snímek">
        <h3>2 · Neměnný snímek</h3>
        <button type="button" disabled={busy || !preview || scopeStale} onClick={createSnapshot}>
          Vytvořit neměnný snímek
        </button>
        {snapshot && (
          <>
            <p>
              Snímek: <code>{snapshot.id}</code> · digest <code>{snapshot.digest}</code>
            </p>
            <button type="button" disabled={busy} onClick={reloadSnapshot}>
              Ověřit uložený snímek
            </button>
            {reloadedSnapshot && (
              <p role="status">Snímek načten neměnný: digest odpovídá ({reloadedSnapshot.digest}).</p>
            )}
          </>
        )}
      </section>

      <section className="v3-section" aria-label="Dokumentační běh">
        <h3>3 · Příprava a spuštění</h3>
        <label className="v3-field">
          Zadání dokumentačního běhu
          <textarea
            aria-label="Zadání dokumentačního běhu"
            value={task}
            maxLength={4000}
            rows={4}
            disabled={active || busy}
            onChange={(e) => {
              generation.current++;
              setTask(e.target.value);
              setRun(null);
              setApproved(false);
              setError("");
            }}
          />
        </label>
        <button
          type="button"
          disabled={busy || active || !snapshot || !validTask}
          onClick={() => snapshot && perform(() => prepareSnapshotRun(snapshot.id, project, workspace, task.trim()))}
        >
          Připravit dokumentační běh
        </button>
        {run && (
          <>
            <h4>{STATUS_LABEL[run.status] || `Neznámý stav: ${run.status}`}</h4>
            <p>
              Běh: <code>{run.id}</code>
            </p>
            {run.status === "prepared" && (
              <>
                <p>Potvrzení spustí běh nad přesně tímto snímkem. Žádný model neběžel při přípravě.</p>
                <label className="v3-check">
                  <input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} />
                  Schvaluji spuštění dokumentačního běhu nad tímto snímkem
                </label>
                <button
                  type="button"
                  disabled={!approved || busy}
                  onClick={() => run && perform(() => startHandoff(run.id, run.digest))}
                >
                  Potvrdit a spustit
                </button>
              </>
            )}
            {active && (
              <>
                <button type="button" disabled={busy || stopPending} onClick={() => setStopRequested(true)}>
                  Zastavit běh
                </button>
                {stopPending && <p role="status">Zastavení bylo vyžádáno; čekám na ověření serverem.</p>}
                {stopRequested && (
                  <div role="group" aria-label="Potvrzení zastavení">
                    <button type="button" disabled={busy} onClick={() => run && perform(() => stopHandoff(run.id))}>
                      Potvrdit zastavení
                    </button>
                    <button type="button" disabled={busy} onClick={() => setStopRequested(false)}>
                      Nezastavovat
                    </button>
                  </div>
                )}
              </>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                // Capture the ticket and the exact run this click targets: if scope changes
                // (generation bumps) while the export is in flight, the old run's response must
                // neither download nor surface an error into the new scope.
                const ticket = generation.current;
                const exportedRun = run;
                try {
                  const value = await exportHandoff(exportedRun.id);
                  if (!mounted.current || ticket !== generation.current) return;
                  if (value.id !== exportedRun.id || value.digest !== exportedRun.digest) {
                    throw new Error("Export neodpovídá běhu.");
                  }
                  download(`opora-run-${exportedRun.id}.json`, JSON.stringify(value, null, 2), "application/json");
                } catch (e) {
                  if (mounted.current && ticket === generation.current) setError(errorMessage(e));
                }
              }}
            >
              Exportovat přesné zadání
            </button>
            {!!run.events?.length && (
              <details>
                <summary>Skutečné události běhu</summary>
                <ol>
                  {run.events.map((event, index) => (
                    <li key={index}>
                      {event.observedAt} {event.kind}
                    </li>
                  ))}
                </ol>
              </details>
            )}
            {run.result && (
              <>
                <pre data-testid="run-result-content">{run.result.content}</pre>
                <p>
                  SHA-256: <code>{run.result.sha256}</code>
                </p>
              </>
            )}
            {run.error && <p role="alert">{run.error}</p>}
          </>
        )}
      </section>
    </section>
  );
}
