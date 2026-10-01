// Dílek Filtr šuplíku: dvě pilulky „Pro tento projekt N“ a „Vše M“ pod hledáním Knihovny i Agentů.
// Čísla dostane hotová, volbu hlásí `onScope` nahoru; ukládá ji rodič jednou pro aplikaci.
import type { CatalogScope } from "@/layout/panel-dock/logic/panel-drawer";

export default function CatalogScopeBar({
  scope,
  fitting,
  all,
  onScope,
}: {
  scope: CatalogScope;
  fitting: number;
  all: number;
  onScope: (scope: CatalogScope) => void;
}) {
  const options: { id: CatalogScope; label: string; count: number }[] = [
    { id: "fitting", label: "Pro tento projekt", count: fitting },
    { id: "all", label: "Vše", count: all },
  ];
  return (
    <div className="catalog-scope" role="group" aria-label="Co z katalogu ukázat">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          className={"catalog-scope__pill" + (scope === option.id ? " catalog-scope__pill--active" : "")}
          aria-pressed={scope === option.id}
          data-testid={"catalog-scope-" + option.id}
          onClick={() => onScope(option.id)}
        >
          {option.label} <span className="catalog-scope__count">{option.count}</span>
        </button>
      ))}
    </div>
  );
}
