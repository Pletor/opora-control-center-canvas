// MVP a distribuce: výběr kapitol do MVP (agent navrhuje, člověk potvrzuje), „Vložit vybrané jako karty“
// a „Rozdistribuovat zbytek plánu“. Obojí sestaví koncept canvas-plan a ukáže náhled (PlanPreview);
// zapíše se až po potvrzení člověkem. Výběr drží tento dílek; kapitoly i karty jsou jen z vybrané stopy
// (předek jiné stopy je cesta, ne řádek k výběru).
import { useMemo, useState } from "react";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import type { CanvasPlanResult } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { flatten } from "../logic/vault-dock-model";
import { buildPlan, defaultSelection, distributeCandidates, selectionCandidates, type VaultPlan } from "../logic/vault-plan";
import { vaultOp, type VaultScope } from "../logic/vault-actions";
import PlanPreview from "./PlanPreview";

function tagOf(node: VaultNode): { label: string; tone: string } {
  if (node.changedSinceInsert) return { label: node.mvp === "yes" ? "MVP · změněno" : "změněno po vložení", tone: "changed" };
  if (node.inserted) return node.mvp === "yes" ? { label: "MVP · vloženo", tone: "mvp" } : { label: "vloženo", tone: "" };
  if (node.mvp === "yes") return { label: "MVP potvrzeno", tone: "mvp" };
  if (node.mvp === "proposed") return { label: "navrženo agentem", tone: "proposed" };
  if (node.mvp === "no") return { label: "mimo MVP", tone: "" };
  return { label: "uloženo", tone: "" };
}

export default function MvpSection({ scope, roots, query, readOnly, digest, parent, onApplied }: {
  scope: VaultScope;
  roots: VaultNode[];
  query: string;
  readOnly: boolean;
  digest: string;
  /** Kam se nové karty vloží (sektor, rodič karty, nebo kořen plátna). */
  parent: string | null;
  onApplied: (result: CanvasPlanResult, message: string) => void;
}) {
  const rows = useMemo(() => flatten(roots).filter((item) => item.node.kind === "brief" && !item.node.offTrack
    && (item.depth > 0 || !item.node.children.some((child) => child.kind === "brief"))), [roots]);
  const [selected, setSelected] = useState<Set<string>>(() => defaultSelection(roots));
  const [preview, setPreview] = useState<{ title: string; plan: VaultPlan } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const shown = rows.filter((item) => !query.trim() || item.node.title.toLocaleLowerCase("cs").includes(query.trim().toLocaleLowerCase("cs")));
  const toInsert = selectionCandidates(roots, selected);
  const rest = distributeCandidates(roots);
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  async function mark(body: Record<string, unknown>, done: string) {
    setBusy(true); setMessage("");
    try { await vaultOp(scope, body); setMessage(done); } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const ids = [...selected];
  return (
    <div className="vault-stack" data-testid="vault-mvp">
      <p className="vault-dock__lead">Vyber, co jde do MVP, a vlož to jako karty. Zbytek plánu rozdistribuuješ jedním krokem, až bude MVP hotové. Agent jen navrhuje, potvrzuješ ty.</p>
      <section className="vault-panel" aria-label="Kapitoly zadání">
        {shown.length ? shown.map((item) => {
          const tag = tagOf(item.node);
          return (
            <label key={item.node.id} className="vault-mvp__row" style={{ paddingLeft: 8 + Math.max(0, item.depth - 1) * 14 }}>
              <input type="checkbox" checked={selected.has(item.node.id)} disabled={readOnly} onChange={() => toggle(item.node.id)} />
              <span className="vault-mvp__title">{item.node.title}</span>
              <span className={"vault-tag" + (tag.tone ? " vault-tag--" + tag.tone : "")}>{tag.label}</span>
            </label>
          );
        }) : <p className="vault-panel__text">{query ? "Hledání nenašlo žádnou kapitolu." : "Schránka nemá kapitoly k výběru."}</p>}
        {!readOnly && (
          <div className="vault-actions">
            <button type="button" className="vault-button" disabled={busy || !ids.length}
              onClick={() => void mark({ op: "propose-mvp", fragmentIds: ids }, "Navrženo do MVP.")}>Navrhnout do MVP</button>
            <button type="button" className="vault-button" disabled={busy || !ids.length}
              onClick={() => void mark({ op: "set-mvp", fragmentIds: ids, mvp: "yes" }, "MVP potvrzeno.")}>Potvrdit MVP ({ids.length})</button>
            <button type="button" className="vault-button" disabled={busy || !ids.length}
              onClick={() => void mark({ op: "set-mvp", fragmentIds: ids, mvp: "no" }, "Vyřazeno z MVP.")}>Vyřadit z MVP</button>
            {message && <span className="vault-dock__notice" role="status">{message}</span>}
          </div>
        )}
      </section>
      {preview ? (
        <PlanPreview scope={scope} digest={digest} plan={preview.plan} title={preview.title} onCancel={() => setPreview(null)}
          onApplied={(result) => { setPreview(null); onApplied(result, `Vloženo ${preview.plan.cards.length} karet s odkazem na schránku.`); }} />
      ) : (
        <div className="vault-grid">
          <section className="vault-panel" aria-label="Vložit vybrané jako karty">
            <h3 className="vault-panel__title">Vložit vybrané jako karty</h3>
            <p className="vault-panel__text">{toInsert.length} {toInsert.length === 1 ? "kapitola" : "kapitol"} bez karty z výběru → karty s odkazem na kapitolu, podkapitoly jako bloky. Nejdřív náhled.</p>
            <button type="button" className="vault-button vault-button--primary" disabled={readOnly || !toInsert.length || !digest}
              onClick={() => setPreview({ title: "Vložit vybrané jako karty", plan: buildPlan(roots, toInsert, parent) })}>Zobrazit náhled a vložit ({toInsert.length})</button>
          </section>
          <section className="vault-panel" aria-label="Rozdistribuovat zbytek plánu">
            <h3 className="vault-panel__title">Rozdistribuovat zbytek plánu</h3>
            <p className="vault-panel__text">{rest.length} nevložených částí → návrh pracovních karet, podkapitoly jako bloky. Nic se nezapíše bez tvého potvrzení.</p>
            <button type="button" className="vault-button" disabled={readOnly || !rest.length || !digest}
              onClick={() => setPreview({ title: "Rozdistribuovat zbytek plánu", plan: buildPlan(roots, rest, parent) })}>Připravit návrh ({rest.length})</button>
          </section>
        </div>
      )}
    </div>
  );
}
