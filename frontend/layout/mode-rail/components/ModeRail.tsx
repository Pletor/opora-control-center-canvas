import { WORKSPACE_MODES, type WorkspaceMode } from "@/shared/surface-settings/logic/workspace-settings";
import { EDITOR_MODES, modeIcon } from "@/layout/mode-rail/logic/mode-rail";
import Icon from "@/ui-kit/icon/components/Icon";

/** Přímé záložky všech pohledů. */
export default function ModeRail({ mode, onMode }: { mode: WorkspaceMode; onMode: (mode: WorkspaceMode) => void }) {
  const meta = (key: string) => WORKSPACE_MODES.find((item) => item.key === key)!;
  return (
    <nav className="mode-rail" aria-label="Pracovní módy">
      {EDITOR_MODES.map((key) => {
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
    </nav>
  );
}
