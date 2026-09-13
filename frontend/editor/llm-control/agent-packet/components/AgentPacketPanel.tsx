import { useEffect, useMemo, useRef, useState } from "react";
import { errorMessage, exportExternalTask, fetchSnapshot, previewPacket, snapshotPacket } from "@/shared/desktop-state/logic/api";
import type { PacketPreviewResponse, PacketSnapshotResponse } from "@/shared/desktop-state/logic/types";

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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [externalExport, setExternalExport] = useState("");
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
  // change must invalidate any in-flight request tied to the old scope AND drop snapshot state
  // that belongs to that old scope, so snapshot/export can never reuse a stale
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
    setError("");
    setExternalExport("");
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
      setExternalExport("");
      setSnapshot(null);
      setReloadedSnapshot(null);
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
      setExternalExport("");
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
      // Readback is validated (id, digest, project/workspace/node) before it can be reported as verified.
      const value = await fetchSnapshot({
        id: snapshot.id,
        digest: snapshot.digest,
        project,
        workspace,
        nodeId: snapshot.packet.scope.nodeId,
      });
      if (!mounted.current || ticket !== generation.current) return;
      setReloadedSnapshot(value);
    } catch (e) {
      if (mounted.current && ticket === generation.current) setError(errorMessage(e));
    } finally {
      if (mounted.current && ticket === generation.current) setBusy(false);
    }
  }

  async function exportForExternalAgent() {
    if (busy || !reloadedSnapshot || !nodeId || scopeStale) return;
    const ticket = ++generation.current;
    setBusy(true);
    setError("");
    setExternalExport("");
    try {
      const value = await exportExternalTask({ id: reloadedSnapshot.id, digest: reloadedSnapshot.digest,
        project, workspace, nodeId });
      if (!mounted.current || ticket !== generation.current) return;
      setExternalExport(value.path);
    } catch (e) {
      if (mounted.current && ticket === generation.current) setError(errorMessage(e));
    } finally {
      if (mounted.current && ticket === generation.current) setBusy(false);
    }
  }

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
            <p className="v3-note">Externí agent: zapíše Markdown do Git workspace vybraného projektu,
              nikoli do jeho mainu. Nevytváří běh ani souhlas s implementací; chybějící zadání zůstane blocked.
              Existující odlišný soubor se nepřepíše.</p>
            <button type="button" disabled={busy || !reloadedSnapshot || !nodeId || scopeStale}
              onClick={exportForExternalAgent}>Exportovat pro externího agenta</button>
            {externalExport && <p role="status">Zapsáno a zpětně ověřeno: <code>{externalExport}</code>.
              Stav a výsledek externího agenta vraťte jako ticket uzlu s autorem agent, bez session ID.
              Workflow fázi posune člověk po ověření.</p>}
          </>
        )}
      </section>

    </section>
  );
}
