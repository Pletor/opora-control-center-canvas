import {useCallback, useEffect, useRef, useState} from "react";
import {api} from "@/shared/types/logic/types";
import FlowEditor from "@/shared/flow-editor/components/FlowEditor";
import type {NodeTypeSpec} from "@/shared/flow-editor/logic/flow-types";
import {loadLibraryTypes} from "../../logic/library-api";
import {operationTitle, reviewRows, scopedReviewId, selectedReview, type LibraryReview} from "../logic/library-reviews";
import "../styles/library-reviews.css";

export default function LibraryReviews({project, workspace, onBack}: {project: string; workspace: string; onBack: () => void}) {
  const [items, setItems] = useState<LibraryReview[]>([]);
  const [selected, setSelected] = useState(() => scopedReviewId(location.search, project, workspace));
  const [node, setNode] = useState<string | null>(null);
  const [types, setTypes] = useState<NodeTypeSpec[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadedScope, setLoadedScope] = useState("");
  const mounted = useRef(true);
  const generation = useRef(0);
  const scope = new URLSearchParams({project, workspace}).toString();
  const reload = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const result = await api<{items: LibraryReview[]}>(`/api/library/reviews?${scope}`);
      if (current === generation.current) { setItems(result.items); setLoadedScope(scope); }
    } catch (caught) { if (current === generation.current) setError(String(caught)); }
    finally { if (current === generation.current) setLoading(false); }
  }, [scope]);
  useEffect(() => {
    mounted.current = true; setItems([]); setError(""); setBusy(false); setSelected(scopedReviewId(location.search, project, workspace));
    void reload();
    return () => { generation.current++; mounted.current = false; };
  }, [reload, project, workspace]);
  useEffect(() => { let active = true; loadLibraryTypes().then(value => { if (active) setTypes(value); }).catch(() => {}); return () => {active = false;}; }, []);
  const visibleItems = loadedScope === scope ? items : [];
  const review = loading || loadedScope !== scope ? null : selectedReview(visibleItems, selected);
  const select = (identifier: string) => {
    setSelected(identifier); setNode(null);
    const query = new URLSearchParams(location.search);
    query.set("project", project); query.set("workspace", workspace); query.set("libraryReview", identifier);
    history.replaceState(null, "", "/?" + query);
  };
  const decide = async (action: "accept" | "reject") => {
    if (!review || busy || review.status !== "pending") return;
    const current = generation.current;
    setBusy(true); setError("");
    try {
      await api(`/api/library/reviews/${encodeURIComponent(review.id)}/${action}`, {project, workspace});
      if (current === generation.current) await reload();
    } catch (caught) { if (current === generation.current) setError(String(caught)); }
    finally { if (mounted.current && current <= generation.current) setBusy(false); }
  };
  return <section className="library-reviews" aria-label="Návrhy knihovny">
    <header><button onClick={onBack}>← Zpět</button><h2>Návrhy knihovny</h2><button disabled={busy} onClick={() => {setError(""); void reload();}}>Obnovit</button></header>
    {error && <p role="alert">{error} Při změně podkladů nechte připravit nový návrh; tento zůstává v historii.</p>}
    <nav aria-label="Historie návrhů">{visibleItems.map(item => <button key={item.id} disabled={busy || loading} aria-pressed={item.id === review?.id} onClick={() => select(item.id)}>{operationTitle[item.operation]} · {item.input.title ?? item.before.folder?.title ?? item.before.source?.name ?? item.id}</button>)}</nav>
    {!review ? <p role={selected && !loading ? "alert" : undefined}>{loading ? "Načítám návrhy…" : selected ? "Vybraný návrh v tomto projektu a prostoru neexistuje. Vyberte návrh z historie." : "Zatím tu nejsou žádné návrhy."}</p> : <article>
      <h3>{operationTitle[review.operation]}</h3>
      <p>{review.status === "pending" ? "Návrh – čeká na vaše rozhodnutí. Knihovna se zatím nezměnila." : review.status === "rejected" ? "Zamítnuto – knihovna se nezměnila." : "Změna byla provedena."}</p>
      <p>Připravil {review.author.name} · {new Date(review.createdAt).toLocaleString("cs-CZ")}</p>
      <table><thead><tr><th>Položka</th><th>Před změnou</th><th>Po změně</th></tr></thead><tbody>{reviewRows(review).map(row => <tr key={row.label}><th>{row.label}</th><td>{row.before || "—"}</td><td>{row.after || "—"}</td></tr>)}</tbody></table>
      {review.before.version && <><p>Použitá verze zdroje: {review.before.version.n}</p><div className="library-reviews__graph"><FlowEditor graph={review.before.version.graph} types={types} readOnly selected={node} onSelect={setNode} onChange={() => {}} frames/></div></>}
      <details><summary>Identifikátory návrhu a zdroje</summary><p>{review.id}</p>{review.before.source && <p>{review.before.source.id} · {review.before.version?.id}</p>}</details>
      {review.requiresHuman && review.status === "pending" && <footer><button disabled={busy} onClick={() => void decide("accept")}>Přijmout a provést změnu</button><button disabled={busy} onClick={() => void decide("reject")}>Zamítnout</button></footer>}
    </article>}
  </section>;
}
