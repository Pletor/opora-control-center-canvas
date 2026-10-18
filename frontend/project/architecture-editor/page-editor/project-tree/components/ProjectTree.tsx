import { useState } from "react";
import "../styles/project-tree.css";
import type { TreeDomain, TreeGroup } from "../logic/project-tree-model";
import PageIcon from "../../components/PageIcon";

type Props = {
  title: string; groups: TreeGroup[]; disabled: boolean;
  onOpenPage: (domainId: string, pageId: string) => void; onAddPage: (domainId: string) => void;
};

/** Read-only project navigation: groups → domains → pages. Structure itself changes only in the project map. */
export default function ProjectTree({ title, groups, disabled, onOpenPage, onAddPage }: Props) {
  const [open, setOpen] = useState<Set<string>>(() => new Set(groups.filter((group) => group.active).map((group) => group.id)));
  const [closedDomains, setClosedDomains] = useState<Set<string>>(new Set());
  const flip = (set: Set<string>, id: string) => { const next = new Set(set); if (next.has(id)) next.delete(id); else next.add(id); return next; };

  function domain(item: TreeDomain) {
    const expanded = !closedDomains.has(item.id);
    return <li key={item.id} className={"project-tree__domain" + (item.active ? " project-tree__domain--active" : "")} data-testid={"architecture-tree-domain-" + item.id}>
      <button type="button" className="project-tree__domain-head" aria-expanded={expanded} onClick={() => setClosedDomains((set) => flip(set, item.id))}>
        <span className="project-tree__caret" aria-hidden="true">{expanded ? "▾" : "▸"}</span>
        <PageIcon name={item.kind} className="project-tree__domain-icon"/>
        <span className="project-tree__domain-text">
          <span className="project-tree__host">{item.host ?? item.name}</span>
          <span className="project-tree__meta">{item.kindLabel}{item.purpose ? ` · ${item.purpose}` : ""}</span>
        </span>
      </button>
      {expanded && <ul className="project-tree__pages">
        {item.pages.map((page) => <li key={page.id} data-testid={"architecture-tree-" + page.id}>
          <button type="button" style={{ paddingLeft: 10 + page.depth * 16 }}
            className={"project-tree__page" + (page.active ? " project-tree__page--active" : "")}
            aria-current={page.active ? "page" : undefined} data-testid={"architecture-open-" + page.id}
            title={page.path ?? undefined} onClick={() => onOpenPage(item.id, page.id)}>
            <PageIcon name="page" size={15} className="project-tree__page-icon"/>{page.name}
          </button>
        </li>)}
        {!item.pages.length && <li className="project-tree__empty">Zatím žádná stránka.</li>}
        <li><button type="button" className="project-tree__add" disabled={disabled} data-testid={"architecture-tree-add-page-" + item.id}
          aria-label={`Přidat stránku do ${item.host ?? item.name} v Mapě domény`} onClick={() => onAddPage(item.id)}>+ Stránka</button></li>
      </ul>}
    </li>;
  }

  return <nav className="project-tree" aria-label="Strom projektu">
    <h3 className="project-tree__title">{title}</h3>
    {groups.map((group) => {
      const expanded = open.has(group.id);
      return <section key={group.id} className={`project-tree__group project-tree__group--${group.tone}`} data-testid={"architecture-tree-group-" + group.tone}>
        <button type="button" className="project-tree__group-head" aria-expanded={expanded} onClick={() => setOpen((set) => flip(set, group.id))}>
          <span className="project-tree__caret" aria-hidden="true">{expanded ? "▾" : "▸"}</span>
          <span className="project-tree__group-label">{group.label}</span>
          {group.badge && <span className="project-tree__badge">{group.badge}</span>}
          <span className="project-tree__count">{group.domains.length}</span>
        </button>
        {expanded && (group.domains.length
          ? <ul className="project-tree__domains">{group.domains.map(domain)}</ul>
          : <p className="project-tree__empty">Zatím žádná doména.</p>)}
      </section>;
    })}
    <p className="project-tree__note">Stránky a jejich pořadí se mění v Mapě domény.</p>
  </nav>;
}
