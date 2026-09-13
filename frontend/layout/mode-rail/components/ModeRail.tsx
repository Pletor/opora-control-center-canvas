import { WORKSPACE_MODES, type WorkspaceMode } from "@/shared/surface-settings/logic/workspace-settings";

/** Jediná navigace módů: úzký rail, jen slova, žádné dekorativní ikony. */
export default function ModeRail({ mode, onMode, editorOnly = false, inactive = false }: { mode: WorkspaceMode; onMode: (mode: WorkspaceMode) => void; editorOnly?: boolean; inactive?: boolean }) {
  return (
    <nav className="mode-rail" aria-label="Pracovní módy">
      {WORKSPACE_MODES.filter((item) => !editorOnly || item.key !== "agents").map((item) => (
        <button
          key={item.key}
          type="button"
          aria-label={"Mód: " + item.label}
          aria-pressed={!inactive && mode === item.key}
          title={item.hint}
          onClick={() => onMode(item.key)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
