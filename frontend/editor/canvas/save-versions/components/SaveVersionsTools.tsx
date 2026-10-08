// Pravý konec lišty Editoru: ikonka Historie uložení a ULOŽIT, pod nimi panel verzí. Skládá dílky
// a drží jen to, jestli je panel otevřený. Data (verze, dirty, ukládání) i obě akce dostává od App,
// které drží stav plátna a po obnovení vymění pohled, stav Desktop v3 a historii Ctrl+Z.
import { useCallback, useState } from "react";
import SaveButton from "@/editor/canvas/save-versions/components/SaveButton";
import SaveHistoryButton from "@/editor/canvas/save-versions/components/SaveHistoryButton";
import SaveHistoryPanel from "@/editor/canvas/save-versions/components/SaveHistoryPanel";
import type { CanvasVersionsState } from "@/editor/canvas/save-versions/logic/use-canvas-versions";
import "@/editor/canvas/save-versions/styles/save-versions.css";

export default function SaveVersionsTools({ versions, disabled, onSave, onRestore, onPrepareRestore, onReloadExternal }: {
  versions: CanvasVersionsState;
  disabled: boolean;
  onSave: () => void;
  onRestore: (versionId: string) => Promise<void>;
  onPrepareRestore: (versionId: string) => Promise<void>;
  onReloadExternal: () => void;
}) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <div className="save-versions" role="group" aria-label="Uložené verze">
      <SaveHistoryButton open={open} onToggle={() => setOpen((value) => !value)} />
      <SaveButton dirty={versions.dirty} saving={versions.saving} disabled={disabled} onSave={onSave} />
      {versions.externalChanged && <button type="button" className="save-versions__external" onClick={onReloadExternal}>Změna mimo toto okno · načíst</button>}
      {open && (
        <SaveHistoryPanel versions={versions.versions} loading={versions.loading} error={versions.error}
          disabled={disabled || versions.saving} onRestore={onRestore} onPrepareRestore={onPrepareRestore} onClose={close} />
      )}
    </div>
  );
}
