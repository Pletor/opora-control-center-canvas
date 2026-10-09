// Know-how schránky: Rozhodnutí (živý text z karet, fragment jen odkazuje), Podklady (materiály karet
// rozsahu) a Podněty (obousměrně s fragmentem: čip fragmentu, nebo „Udělat z toho fragment“).
import { useState } from "react";
import type { Decision, NodeMaterial } from "@/shared/desktop-state/logic/types";
import type { VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import type { CardIdea } from "@/editor/node-detail/ideas/logic/ideas-model";
import { flatten, fold, safeHref } from "../logic/vault-window-model";
import { vaultOp, type VaultScope } from "../logic/vault-actions";

const hit = (text: string, query: string) => !query.trim() || fold(text).includes(fold(query.trim()));

export function DecisionsSection({ scope, roots, decisions, inScope, nodeNames, query, readOnly }: {
  scope: VaultScope; roots: VaultNode[]; decisions: Decision[]; inScope: Set<string>; nodeNames: Record<string, string>; query: string; readOnly: boolean;
}) {
  const fragments = flatten(roots).map((item) => item.node).filter((node) => node.kind === "brief");
  const linkedBy = new Map<string, VaultNode[]>();
  fragments.forEach((node) => (node.decisions ?? []).forEach((id) => linkedBy.set(id, [...(linkedBy.get(id) ?? []), node])));
  const [target, setTarget] = useState(fragments[0]?.id ?? "");
  const [message, setMessage] = useState("");
  const linked = decisions.filter((item) => linkedBy.has(item.id) && hit(item.text, query));
  const missing = [...linkedBy.keys()].filter((id) => !decisions.some((item) => item.id === id));
  const nearby = decisions.filter((item) => !linkedBy.has(item.id) && inScope.has(item.nodeId) && hit(item.text, query));
  async function link(decisionId: string) {
    const fragment = fragments.find((node) => node.id === target);
    if (!fragment) return;
    try {
      await vaultOp(scope, { op: "link-decisions", fragmentId: fragment.id, decisionIds: [...(fragment.decisions ?? []), decisionId] });
      setMessage(`Rozhodnutí odkázáno z „${fragment.title}“.`);
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
  }
  return (
    <div className="vault-stack" data-testid="vault-decisions">
      <p className="vault-window__lead">Rozhodnutí žijí na kartách; schránka je ukazuje u kapitoly, které se týkají, a nekopíruje je.</p>
      <section className="vault-panel" aria-label="Odkázaná rozhodnutí">
        {linked.length ? linked.map((item) => (
          <div key={item.id} className="vault-row">
            <span className="vault-row__main">{item.text}</span>
            <span className="vault-row__side">{(linkedBy.get(item.id) ?? []).map((node) => node.title).join(", ")} · {nodeNames[item.nodeId] ?? "karta"}</span>
          </div>
        )) : <p className="vault-panel__text">Žádný fragment zatím neodkazuje na rozhodnutí.</p>}
        {missing.length > 0 && <p className="vault-panel__text">Na plátně už není {missing.length} odkázaných rozhodnutí.</p>}
      </section>
      {nearby.length > 0 && (
        <section className="vault-panel" aria-label="Rozhodnutí karet v rozsahu">
          <h3 className="vault-panel__title">Rozhodnutí karet v rozsahu (neodkázaná)</h3>
          {!readOnly && fragments.length > 0 && (
            <label className="vault-field">Odkázat z fragmentu
              <select value={target} onChange={(event) => setTarget(event.target.value)}>
                {fragments.map((node) => <option key={node.id} value={node.id}>{node.title}</option>)}
              </select>
            </label>
          )}
          {nearby.map((item) => (
            <div key={item.id} className="vault-row">
              <span className="vault-row__main">{item.text}</span>
              <span className="vault-row__side">{nodeNames[item.nodeId] ?? "karta"}</span>
              {!readOnly && fragments.length > 0 && <button type="button" className="vault-button" onClick={() => void link(item.id)}>Odkázat</button>}
            </div>
          ))}
          {message && <p className="vault-window__notice" role="status">{message}</p>}
        </section>
      )}
    </div>
  );
}

export function MaterialsSection({ materials, nodeNames, query }: { materials: { nodeId: string; item: NodeMaterial }[]; nodeNames: Record<string, string>; query: string }) {
  const items = materials.filter(({ item }) => hit(item.caption + " " + item.path, query));
  return (
    <div className="vault-stack" data-testid="vault-materials">
      <p className="vault-window__lead">Podklady karet v rozsahu schránky: návrhy, odkazy a soubory, ze kterých zadání vychází.</p>
      {items.length ? <section className="vault-panel">{items.map(({ nodeId, item }) => {
        const href = item.kind === "link" ? safeHref(item.path) : undefined;
        return (
          <div key={nodeId + item.id} className="vault-row">
            <span className="vault-row__main"><strong>{item.caption || item.path}</strong><br />
              {href ? <a href={href} target="_blank" rel="noopener noreferrer">{item.path}</a> : <code>{item.path}</code>}</span>
            <span className="vault-row__side">{nodeNames[nodeId] ?? "karta"}</span>
          </div>
        );
      })}</section> : <div className="vault-window__empty">Žádné podklady. Přidáš je na kartě (port Podklady); schránka je tu sebere.</div>}
    </div>
  );
}

export function IdeasSection({ scope, roots, ideas, nodeNames, vaultScope, query, readOnly, onLinked }: {
  scope: VaultScope; roots: VaultNode[]; ideas: { nodeId: string; idea: CardIdea }[];
  nodeNames: Record<string, string>; vaultScope: string; query: string; readOnly: boolean; onLinked: () => void;
}) {
  const titles = Object.fromEntries(flatten(roots).map((item) => [item.node.id, item.node.title]));
  const [message, setMessage] = useState("");
  const items = ideas.filter(({ idea }) => hit(idea.text, query));
  async function makeFragment(nodeId: string, ideaId: string) {
    try {
      await vaultOp(scope, { op: "from-idea", nodeId, ideaId, ...(roots[0] ? { parentId: roots[0].id } : { scopeNodeId: vaultScope }) });
      onLinked();
      setMessage("Fragment vznikl a Podnět na něj odkazuje.");
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
  }
  return (
    <div className="vault-stack" data-testid="vault-ideas">
      <p className="vault-window__lead">Podněty review a kritiků k dalšímu vývoji. Z Podnětu uděláš fragment zadání; Podnět pak ukazuje, kam patří.</p>
      {items.length ? <section className="vault-panel">{items.map(({ nodeId, idea }) => (
        <div key={nodeId + idea.id} className="vault-row">
          <span className="vault-row__main">{idea.text}</span>
          <span className="vault-row__side">{nodeNames[nodeId] ?? "karta"}{idea.status === "done" ? " · hotovo" : ""}</span>
          {idea.fragmentId ? <span className="brief-chip" title="Fragment schránky vzniklý z Podnětu">{titles[idea.fragmentId] ?? "fragment mimo rozsah"}</span>
            : !readOnly && <button type="button" className="vault-button" onClick={() => void makeFragment(nodeId, idea.id)}>Udělat z toho fragment</button>}
        </div>
      ))}</section> : <div className="vault-window__empty">Žádné Podněty v rozsahu schránky.</div>}
      {message && <p className="vault-window__notice" role="status">{message}</p>}
    </div>
  );
}
