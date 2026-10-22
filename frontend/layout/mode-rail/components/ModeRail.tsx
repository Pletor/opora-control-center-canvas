import { WORKSPACE_MODES, type WorkspaceMode } from "@/shared/surface-settings/logic/workspace-settings";
import { OVERFLOW_MODES, PRIMARY_MODES, isOverflowMode, modeIcon } from "@/layout/mode-rail/logic/mode-rail";
import Icon from "@/ui-kit/icon/components/Icon";
import ToolbarMenu from "@/ui-kit/toolbar-menu/components/ToolbarMenu";

/**
 * Navigace módů na začátku lišty Editoru (návrh „Opora Editor — lean“, rám 1a): tři hlavní pohledy
 * Struktura · Velín · Text jako záložky a vzácnější Kreslení · Kancelář · Storyboard v nabídce ⋯. Aktivní
 * mód svítí akcentem; je-li aktivní mód z nabídky, ⋯ nese jeho jméno, aby bylo jasné, kde člověk je.
 * V úzkém okně popisek zmizí jen vizuálně, jméno dál nese `aria-label` i `title`.
 */
export default function ModeRail({ mode, onMode }: { mode: WorkspaceMode; onMode: (mode: WorkspaceMode) => void }) {
  const meta = (key: string) => WORKSPACE_MODES.find((item) => item.key === key)!;
  const overflowActive = isOverflowMode(mode);
  return (
    <nav className="mode-rail" aria-label="Pracovní módy">
      {PRIMARY_MODES.map((key) => {
        const item = meta(key);
        const active = mode === key;
        return (
          <button key={key} type="button" className={"mode-rail__button" + (active ? " mode-rail__button--active" : "")}
            aria-label={"Mód: " + item.label} aria-pressed={active} title={item.label + ": " + item.hint} onClick={() => onMode(key)}>
            <span className="mode-rail__glyph"><Icon name={modeIcon(key)} size={16} /></span>
            <span className="mode-rail__label">{item.label}</span>
          </button>
        );
      })}
      <ToolbarMenu label={overflowActive ? <>⋯ <span className="mode-rail__label">{meta(mode).label}</span></> : "⋯"} title="Další pohledy"
        heading="Další pohledy" active={overflowActive} onSelect={(key) => onMode(key as WorkspaceMode)}
        items={OVERFLOW_MODES.map((key) => ({ key, label: meta(key).label, hint: meta(key).hint, active: mode === key,
          glyph: <Icon name={modeIcon(key)} size={16} /> }))} />
    </nav>
  );
}
