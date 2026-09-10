import { WORKSPACE_MODES, type WorkspaceMode } from "./workspace-settings";

/** Jediná navigace módů: úzký rail, jen slova, žádné dekorativní ikony. */
export default function ModeRail({ mode, onMode }: { mode: WorkspaceMode; onMode: (mode: WorkspaceMode) => void }) {
  return (
    <nav className="mode-rail" aria-label="Pracovní módy">
      {WORKSPACE_MODES.map((item) => (
        <button
          key={item.key}
          type="button"
          aria-label={"Mód: " + item.label}
          aria-pressed={mode === item.key}
          title={item.hint}
          onClick={() => onMode(item.key)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
