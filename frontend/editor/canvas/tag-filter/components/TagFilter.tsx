// Filtr štítků v liště Editoru: seznam štítků z bloků vrstvy s počty; vybraný štítek ztlumí ostatní karty.
import { tagCounts } from "@/editor/canvas/tag-filter/logic/tag-filter-model";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { Graph } from "@/shared/types/logic/types";
import "@/editor/canvas/tag-filter/styles/tag-filter.css";

export default function TagFilter({
  graph,
  parent,
  state,
  value,
  onChange,
}: {
  graph: Graph;
  parent: string | null;
  state: DesktopState;
  value: string;
  onChange: (tag: string) => void;
}) {
  const counts = tagCounts(graph, parent, state);
  if (counts.length === 0 && !value) return null;
  return (
    <div className="tag-filter" role="group" aria-label="Filtr štítků">
      <span className="tag-filter-label">Štítky</span>
      {counts.map((item) => (
        <button
          key={item.tag}
          type="button"
          className={"tag-filter-chip" + (item.tag === value ? " is-active" : "")}
          aria-pressed={item.tag === value}
          onClick={() => onChange(item.tag === value ? "" : item.tag)}
        >
          {item.tag} <b>{item.count}</b>
        </button>
      ))}
      {value && (
        <button type="button" className="tag-filter-clear" onClick={() => onChange("")}>
          Zrušit filtr
        </button>
      )}
    </div>
  );
}
