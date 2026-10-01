// Hlavička stránky Text: název vrstvy, krátká nápověda k psaní a řádek ovládání — podzáložky
// Uživatel/Agenti a na podzáložce Uživatel stav kapitol „rozbaleno X z Y“ s Rozbalit vše / Sbalit vše.
// Dílek jen hlásí kliky nahoru; kapitoly i podzáložku drží rodič.
import type { TextSubtab } from "@/editor/node-detail/content/components/TextWorkspace";

const SUBTABS: { key: TextSubtab; label: string }[] = [
  { key: "user", label: "Uživatel" },
  { key: "agents", label: "Agenti" },
];

export default function TextWorkspaceHead({
  title, subtab, onSubtab, expandedCount, totalCount, onExpandAll, onCollapseAll,
}: {
  title: string;
  subtab: TextSubtab;
  onSubtab: (subtab: TextSubtab) => void;
  expandedCount: number;
  totalCount: number;
  onExpandAll: () => void;
  onCollapseAll: () => void;
}) {
  return (
    <header className="text-head">
      <h2>{title}</h2>
      <p className="muted">
        Enter přidá blok, Tab zanoří, <kbd>/</kbd> otevře příkazy, <kbd>[[</kbd> odkáže na uzel. Bloky se ukládají samy; zdrojový text ručně.
      </p>
      <div className="text-workspace__bar">
        <div className="text-workspace__subtabs" role="tablist" aria-label="Uživatel nebo Agenti">
          {SUBTABS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={subtab === item.key}
              className={"text-workspace__subtab" + (subtab === item.key ? " text-workspace__subtab--active" : "")}
              onClick={() => onSubtab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {subtab === "user" && totalCount > 0 && (
          <div className="text-workspace__chapters" data-testid="text-chapters-bulk">
            <span className="text-workspace__count">rozbaleno {expandedCount} z {totalCount}</span>
            <button type="button" className="text-workspace__bulk" onClick={onExpandAll} disabled={expandedCount === totalCount}>
              Rozbalit vše
            </button>
            <button type="button" className="text-workspace__bulk" onClick={onCollapseAll} disabled={expandedCount === 0}>
              Sbalit vše
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
