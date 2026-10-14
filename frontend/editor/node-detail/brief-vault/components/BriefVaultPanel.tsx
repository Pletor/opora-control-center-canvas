// Strom schránky: pruh pokrytí, strom fragmentů s kuličkou stavu a pruhem osmi bran a detail vybraného
// fragmentu (sekce Zadání Schránky v levém menu). Uzel jiné disciplíny, který zůstal jen jako cesta ke kořeni,
// je ztlumený; slepá ulička (rozhodnuto: ne) také, s popiskem. Strom dodá rodič (useBriefVault), detail si
// dílek načte sám; klik na čip karty bublá přes onOpenNode a akce nad fragmentem (disciplína, brány, výzkum,
// otázka) dodá rodič v `detailActions` nad načteným detailem.
import { useMemo, useState, type ReactNode } from "react";
import { countChangedMvp, coverageOf, statusDot, textRevisionOf, type FragmentDetail, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import CoverageBar from "@/editor/node-detail/brief-vault/components/CoverageBar";
import FragmentDetailView from "@/editor/node-detail/brief-vault/components/FragmentDetailView";
import GateBar from "@/editor/node-detail/brief-vault/components/GateBar";
import "@/editor/node-detail/brief-vault/styles/brief-vault.css";

export default function BriefVaultPanel({
  project,
  workspace,
  roots,
  loading,
  readOnly,
  error,
  scopeLabel,
  nodeNames,
  onOpenNode,
  initialSelected = null,
  detailActions,
  emptyHint,
}: {
  project: string;
  workspace: string;
  /** Kořeny schránky tohoto rozsahu (plátno, sektor nebo karta). */
  roots: VaultNode[];
  loading: boolean;
  /** Main: schránka žije jen v pracovním prostoru. */
  readOnly: boolean;
  error: string;
  scopeLabel: string;
  nodeNames: Record<string, string>;
  onOpenNode: (id: string) => void;
  /** Fragment, který se má hned otevřít (klik na čip „Ze schránky“). */
  initialSelected?: string | null;
  /** Akce nad vybraným fragmentem od rodiče (disciplína, brány, výzkum, otázka) nad načteným detailem. */
  detailActions?: (id: string, detail: FragmentDetail) => ReactNode;
  /** Vlastní text prázdného výsledku (např. hledání bez shody). */
  emptyHint?: ReactNode;
}) {
  const [selected, setSelected] = useState<string | null>(initialSelected);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const coverage = useMemo(() => coverageOf(roots), [roots]);
  const changedMvp = useMemo(() => countChangedMvp(roots), [roots]);
  const toggle = (id: string) => setExpanded((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  if (error && !roots.length) return <p className="error" role="alert">Schránku nelze načíst: {error}</p>;
  if (loading) return <p className="muted" role="status">Načítám schránku…</p>;
  if (readOnly) return <p className="brief-vault__empty">Main je jen ke čtení. Schránka zadání žije v pracovním prostoru; přepněte do něj.</p>;
  if (!roots.length && emptyHint) return <div className="brief-vault__empty">{emptyHint}</div>;
  if (!roots.length) {
    return (
      <div className="brief-vault__empty" data-testid="brief-vault-empty">
        <p><strong>Schránka {scopeLabel} je prázdná.</strong></p>
        <p>Sem se ukládá dlouhé zadání doslova a s historií verzí: agent nebo člověk ho vloží, rozdělí na kapitoly,
          vybere MVP a jen vybrané kapitoly vloží jako karty. Zbytek tu zůstane „uloženo“ na později a nic se neztratí.</p>
        <p className="muted">Vložení a rozdělení dělá agent přes <code>/api/brief-vault</code> (recept ve skillu OPORA); výzkum, otázky, MVP a vložení jako karty jsou v dalších sekcích Schránky.</p>
      </div>
    );
  }
  return (
    <div className="brief-vault" data-testid="brief-vault">
      <CoverageBar coverage={coverage} changedMvp={changedMvp} />
      {error && <p className="muted" role="status">Obnovení selhalo, ukazuji poslední načtený stav.</p>}
      <ul className="brief-vault__tree" role="tree" aria-label={"Schránka " + scopeLabel}>
        {roots.map((root) => (
          <TreeRow key={root.id} node={root} depth={0} expanded={expanded} selected={selected}
            onToggle={toggle} onSelect={(id) => setSelected((current) => (current === id ? null : id))} />
        ))}
      </ul>
      {selected && (
        <FragmentDetailView key={selected} project={project} workspace={workspace} id={selected}
          nodeNames={nodeNames} onOpenNode={onOpenNode} onClose={() => setSelected(null)} refresh={roots}
          actions={detailActions ? (detail) => detailActions(selected, detail) : undefined} />
      )}
    </div>
  );
}

function TreeRow({ node, depth, expanded, selected, onToggle, onSelect }: {
  node: VaultNode;
  depth: number;
  expanded: Set<string>;
  selected: string | null;
  onToggle: (id: string) => void;
  onSelect: (id: string) => void;
}) {
  const open = expanded.has(node.id);
  const dot = statusDot(node);
  const latestRef = node.cards.length ? Math.min(...node.cards.map((card) => card.revision)) : null;
  return (
    <li role="treeitem" aria-expanded={node.children.length ? open : undefined} aria-selected={selected === node.id}>
      <div className={"brief-vault__row" + (selected === node.id ? " brief-vault__row--selected" : "") + (node.offPath ? " brief-vault__row--path" : "") + (node.deadEnd ? " brief-vault__row--dead" : "")}
        style={{ paddingLeft: 4 + depth * 14 }}>
        {node.children.length ? (
          <button type="button" className="brief-vault__twist" aria-label={(open ? "Sbalit: " : "Rozbalit: ") + node.title}
            onClick={() => onToggle(node.id)}>{open ? "▾" : "▸"}</button>
        ) : <span className="brief-vault__twist" aria-hidden="true" />}
        <span className={"brief-vault__dot brief-vault__dot--" + dot.tone} title={dot.label} aria-hidden="true" />
        <button type="button" className="brief-vault__title" onClick={() => onSelect(node.id)}
          title={`${node.title} · ${dot.label} · r${node.revision}`}>
          {node.kind === "research" && <span className="brief-vault__kind">výzkum: </span>}
          {node.kind === "question" && <span className="brief-vault__kind">otázka: </span>}
          {node.title}
        </button>
        {node.kind === "brief" && node.gates && <GateBar node={node} />}
        <span className="brief-vault__state" title={node.deadEnd ? "Rozhodnuto: ne. Důvod je v detailu fragmentu (brána Rozhodnuto)." : undefined}>
          {node.offPath ? "jiná disciplína · cesta" : node.deadEnd ? "slepá ulička" : dot.label}
        </span>
        {node.cards.length > 0 && <span className="brief-vault__meta" title="Karty vzniklé z fragmentu">→ {node.cards.length}</span>}
        {node.changedSinceInsert && (
          <span className="brief-vault__changed" title="Karta vznikla ze starší revize textu fragmentu">⚠ v{textRevisionOf(node)} &gt; v{latestRef}</span>
        )}
        {node.ideas > 0 && <span className="brief-vault__meta" title="Otevřené Podněty k fragmentu">💡{node.ideas}</span>}
        {!!node.hidden && <span className="brief-vault__meta" title="Hlubší větev pod stropem hloubky stromu">+{node.hidden} hlouběji</span>}
      </div>
      {open && node.children.length > 0 && (
        <ul role="group" className="brief-vault__tree">
          {node.children.map((child) => (
            <TreeRow key={child.id} node={child} depth={depth + 1} expanded={expanded} selected={selected}
              onToggle={onToggle} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  );
}
