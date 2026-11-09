import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/types/logic/types";

type Review = { id: string; digest: string; operation: string; author: { name: string }; payload: Record<string, unknown>; targets: { id: string; name: string; kind: string }[]; observed: { stateRevision: number } };
type Readback = { state: string; review: Review };
export async function runScopedReview(action: () => Promise<unknown>, current: () => boolean, success: () => void, failure: (error: unknown) => void, finish: () => void) {
  try { await action(); if (current()) success(); }
  catch (error) { if (current()) failure(error); }
  finally { if (current()) finish(); }
}
export function selectedDesktopReview(search: string, project: string, workspace: string) {
  const query = new URLSearchParams(search);
  const id = query.get("desktopReview");
  return query.get("project") === project && query.get("workspace") === workspace && id && /^[A-Za-z0-9_.:-]{1,160}$/.test(id) ? id : null;
}
const labels: Record<string, string> = { grant_autonomy: "Svěření autonomie sektoru", confirm_sector_proposals: "Potvrzení navržených karet", review_rule: "Posouzení pravidla", review_rules: "Posouzení pravidel" };
export default function DesktopReview({ project, workspace }: { project: string; workspace: string }) {
  const identifier = selectedDesktopReview(window.location.search, project, workspace);
  const scopeKey = JSON.stringify([project, workspace, identifier]);
  const scope = useRef({ key: scopeKey, live: true });
  if (scope.current.key !== scopeKey) { scope.current.live = false; scope.current = { key: scopeKey, live: true }; }
  const [value, setValue] = useState<Readback | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [applied, setApplied] = useState(false);
  const [closed, setClosed] = useState(false);
  useEffect(() => {
    if (!identifier) return;
    const captured = scope.current;
    captured.live = true;
    let live = true;
    setValue(null); setError(""); setApplied(false); setClosed(false); setBusy(false);
    const q = new URLSearchParams({ project, workspace });
    void api<Readback>(`/api/desktop-reviews/${encodeURIComponent(identifier)}?${q}`).then(result => { if (live) { setValue(result); setApplied(result.state === "applied"); } })
      .catch(cause => { if (live) setError(String(cause)); });
    return () => { live = false; captured.live = false; };
  }, [project, workspace, identifier]);
  if (!identifier || closed) return null;
  const close = () => { const url = new URL(window.location.href); url.searchParams.delete("desktopReview"); history.replaceState(null, "", url); setClosed(true); };
  const apply = async () => {
    if (!value || value.state !== "ready" || busy) return;
    const captured = scope.current;
    setBusy(true); setError("");
    await runScopedReview(() => api(`/api/desktop-reviews/${encodeURIComponent(identifier)}/apply`, { project, workspace, digest: value.review.digest }),
      () => captured.live && scope.current === captured, () => setApplied(true), cause => setError(String(cause)), () => setBusy(false));
  };
  return <section role="dialog" aria-label="Desktop review" style={{ position: "fixed", right: 16, top: 96, width: "min(520px, calc(100vw - 32px))", maxHeight: "calc(100vh - 112px)", overflow: "auto", zIndex: 100, background: "var(--surface)", color: "var(--text)", border: "1px solid var(--line)", borderRadius: 8, padding: 16 }}>
    <button onClick={close} disabled={busy}>Zavřít</button>
    <h2>{value ? labels[value.review.operation] : "Posouzení návrhu"}</h2>
    {error && <p role="alert">{error}</p>}
    {value && <><p>Navrhl: {value.review.author.name}. Pozorovaná revize: {value.review.observed.stateRevision}.</p>
      <p>Posuzujete přesně uložený návrh. Změna stavu vyžaduje nové posouzení.</p>
      <ul>{value.review.targets.map(target => <li key={target.id}>{target.name}</li>)}</ul>
      {value.review.operation === "grant_autonomy" ? <><p>Platnost: {String(value.review.payload.until || "Odebrat autonomii")}</p><p>{String(value.review.payload.note)}</p></> : null}
      {value.review.operation === "confirm_sector_proposals" ? <p>Potvrdit návrhy agenta u vybraných karet v tomto sektoru.</p> : null}
      {value.review.operation.startsWith("review_rule") ? <><p>{value.review.payload.decision === "approve" ? "Schválit pravidla" : "Zamítnout pravidla"}</p>
        <ul>{(value.review.operation === "review_rule" ? [{ expected: value.review.payload.expected }] : value.review.payload.items as { expected: unknown }[]).map((item, index) => <li key={index}>{String((item.expected as { text: string }).text)}</li>)}</ul></> : null}
      {applied ? <p role="status">Změna byla provedena.</p> : value.state === "incomplete" ? <p role="alert">{"Nedokon\u010den\u00fd z\u00e1znam operace. Nativn\u00ed zm\u011bna ji\u017e mohla prob\u011bhnout. Zkontrolujte aktu\u00e1ln\u00ed stav; akci neopakujte naslepo."}</p> : value.state !== "ready" ? <p role="alert">Návrh je zastaralý. Zkontrolujte aktuální stav; tento návrh nelze provést.</p> : <button disabled={busy} onClick={() => void apply()}>Potvrdit a provést přesný návrh</button>}</>}
  </section>;
}
