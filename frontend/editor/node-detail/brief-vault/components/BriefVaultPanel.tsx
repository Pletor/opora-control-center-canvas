// Záložka Schránka: pruh pokrytí, strom fragmentů s kuličkou stavu a detail vybraného fragmentu.
// Jen čtení. Strom dodá rodič (useBriefVault), detail si dílek načte sám; klik na čip karty bublá přes onOpenNode.
import { useMemo, useState } from "react";
import {
  COVERAGE_SEGMENTS, coverageOf, coverageSegments, statusDot, type VaultNode,
} from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import FragmentDetailView from "@/editor/node-detail/brief-vault/components/FragmentDetailView";
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
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const coverage = useMemo(() => coverageOf(roots), [roots]);
  const segments = coverageSegments(coverage);
  const toggle = (id: string) => setExpanded((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  if (error && !roots.length) return <p className="error" role="alert">Schránku nelze načíst: {error}</p>;
  if (loading) return <p className="muted" role="status">Načítám schránku…</p>;
  if (readOnly) return <p className="brief-vault__empty">Main je jen ke čtení. Schránka zadání žije v pracovním prostoru; přepněte do něj.</p>;
  if (!roots.length) {
    return (
      <div className="brief-vault__empty" data-testid="brief-vault-empty">
        <p><strong>Schránka {scopeLabel} je prázdná.</strong></p>
        <p>Sem se ukládá dlouhé zadání doslova a s historií verzí: agent nebo člověk ho vloží, rozdělí na kapitoly,
          vybere MVP a jen vybrané kapitoly vloží jako karty. Zbytek tu zůstane „uloženo“ na později a nic se neztratí.</p>
        <p className="muted">Vložení a rozdělení zatím dělá agent přes <code>/api/brief-vault</code> (recept ve skillu OPORA).</p>
      </div>
    );
  }
  return (
    <div className="brief-vault" data-testid="brief-vault">
      <div className="brief-vault__coverage">
        <div className="brief-vault__bar" role="img"
          aria-label={`Pokrytí: ${coverage.leaves} kapitol, ` + COVERAGE_SEGMENTS.map((s) => `${s.label} ${coverage[s.key]}`).join(", ")}>
          {segments.map((segment) => (
            <span key={segment.key} className={"brief-vault__segment brief-vault__segment--" + segment.key}
              style={{ width: segment.percent + "%" }} title={`${segment.label}: ${segment.count}`} />
          ))}
        </div>
        <p className="brief-vault__legend">
          <strong>{coverage.leaves} {coverage.leaves === 1 ? "kapitola" : coverage.leaves < 5 ? "kapitoly" : "kapitol"}:</strong>{" "}
          {COVERAGE_SEGMENTS.map((segment, index) => (
            <span key={segment.key} className={"brief-vault__legend-item" + (coverage[segment.key] ? "" : " brief-vault__legend-item--zero")}>
              {index > 0 && " · "}
              <i className={"brief-vault__swatch brief-vault__segment--" + segment.key} aria-hidden="true" />
              {segment.label} {coverage[segment.key]}
            </span>
          ))}
        </p>
      </div>
      {error && <p className="muted" role="status">Obnovení selhalo, ukazuji poslední načtený stav.</p>}
      <ul className="brief-vault__tree" role="tree" aria-label={"Schránka " + scopeLabel}>
        {roots.map((root) => (
          <TreeRow key={root.id} node={root} depth={0} expanded={expanded} selected={selected}
            onToggle={toggle} onSelect={(id) => setSelected((current) => (current === id ? null : id))} />
        ))}
      </ul>
      {selected && (
        <FragmentDetailView key={selected} project={project} workspace={workspace} id={selected}
          nodeNames={nodeNames} onOpenNode={onOpenNode} onClose={() => setSelected(null)} refresh={roots} />
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
      <div className={"brief-vault__row" + (selected === node.id ? " brief-vault__row--selected" : "")}
        style={{ paddingLeft: 4 + depth * 14 }}>
        {node.children.length ? (
          <button type="button" className="brief-vault__twist" aria-label={(open ? "Sbalit: " : "Rozbalit: ") + node.title}
            onClick={() => onToggle(node.id)}>{open ? "▾" : "▸"}</button>
        ) : <span className="brief-vault__twist" aria-hidden="true" />}
        <span className={"brief-vault__dot brief-vault__dot--" + dot.tone} title={dot.label} aria-hidden="true" />
        <button type="button" className="brief-vault__title" onClick={() => onSelect(node.id)}
          title={`${node.title} · ${dot.label} · r${node.revision}`}>
          {node.kind === "research" && <span className="brief-vault__kind">research: </span>}
          {node.title}
        </button>
        <span className="brief-vault__state">{dot.label}</span>
        {node.cards.length > 0 && <span className="brief-vault__meta" title="Karty vzniklé z fragmentu">→ {node.cards.length}</span>}
        {node.changedSinceInsert && (
          <span className="brief-vault__changed" title="Karta vznikla ze starší revize fragmentu">⚠ v{node.revision} &gt; v{latestRef}</span>
        )}
        {node.ideas > 0 && <span className="brief-vault__meta" title="Otevřené Podněty k fragmentu">💡{node.ideas}</span>}
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
