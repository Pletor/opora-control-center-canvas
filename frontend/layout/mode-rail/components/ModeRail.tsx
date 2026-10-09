import { WORKSPACE_MODES, type WorkspaceMode } from "@/shared/surface-settings/logic/workspace-settings";
import { modeIcon } from "@/layout/mode-rail/logic/mode-rail";
import Icon from "@/ui-kit/icon/components/Icon";

/**
 * Jediná navigace módů: vodorovné záložky na začátku lišty nástrojů Editoru — kontrakt „Rozvržení
 * Editoru“ (docs/rozvrzeni-editoru.md, Dílek 1). Každá záložka je ikona vlevo od popisku; aktivní
 * mód svítí akcentem a nese spodní linku. V úzkém okně popisek zmizí jen vizuálně, jméno dál nese
 * `aria-label` i `title`. Knihovna tu už není — otevírá ji menu ☰ v `layout/panel-dock/`.
 */
export default function ModeRail({ mode, onMode }: { mode: WorkspaceMode; onMode: (mode: WorkspaceMode) => void }) {
  return (
    <nav className="mode-rail" aria-label="Pracovní módy">
      {WORKSPACE_MODES.map((item) => {
        const active = mode === item.key;
        return (
          <button
            key={item.key}
            type="button"
            className={"mode-rail__button" + (active ? " mode-rail__button--active" : "")}
            aria-label={"Mód: " + item.label}
            aria-pressed={active}
            title={item.label + ": " + item.hint}
            onClick={() => onMode(item.key)}
          >
            <span className="mode-rail__glyph">
              <Icon name={modeIcon(item.key)} size={16} />
            </span>
            <span className="mode-rail__label">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
