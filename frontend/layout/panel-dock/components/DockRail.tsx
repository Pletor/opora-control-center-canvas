// Dílek Lišta ikon: svislý pás 56 px u levého okraje Editoru. Shora Knihovna, Agenti, Postupy,
// oddělovač a Nastavení. Ikona aktivní sekce svítí (`aria-pressed`); klik hlásí `onSelect` a o tom,
// jestli se panel otevře, přepne, nebo sbalí, rozhoduje rodič (pravidla v `logic/panel-dock.ts`).
import DockIcon from "@/layout/panel-dock/components/DockIcon";
import { DOCK_SECTIONS, type DockSection } from "@/layout/panel-dock/logic/panel-dock";

export default function DockRail({ section, onSelect }: { section: DockSection | null; onSelect: (section: DockSection) => void }) {
  return (
    <nav id="panel-dock-rail" className="dock-rail" aria-label="Menu Editoru" data-testid="dock-rail">
      {DOCK_SECTIONS.map((item) => {
        const active = section === item.key;
        const title = item.label + (item.shortcut ? ` (${item.shortcut})` : "");
        return [
          item.apart ? <span key={item.key + "-gap"} className="dock-rail__divider" aria-hidden /> : null,
          <button
            key={item.key}
            type="button"
            className={"dock-rail__button" + (active ? " dock-rail__button--active" : "")}
            aria-label={item.label}
            aria-pressed={active}
            aria-controls={active ? "panel-dock" : undefined}
            title={title}
            data-testid={"dock-section-" + item.key}
            onClick={() => onSelect(item.key)}
          >
            <DockIcon name={item.icon} size={20} />
          </button>,
        ];
      })}
    </nav>
  );
}
