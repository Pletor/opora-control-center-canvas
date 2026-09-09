import { useEffect, useRef } from "react";
import type { SurfaceSettings } from "./workspace-settings";
export default function WorkspaceSettings({
  value,
  onChange,
  onClose,
}: {
  value: SurfaceSettings;
  onChange: (value: SurfaceSettings) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current!;
    d.showModal();
    return () => d.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="removal-dialog"
      aria-labelledby="settings-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <h2 id="settings-title">Nastavení pracovní plochy</h2>
      <p>Preference tohoto prohlížeče. Nemění zadání ani soubory projektu.</p>
      <h3>Struktura a mapa</h3>
      <label className="check">
        <input
          type="checkbox"
          checked={value.showGrid}
          onChange={(e) => onChange({ ...value, showGrid: e.target.checked })}
        />
        Zobrazit mřížku
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={value.snap}
          onChange={(e) => onChange({ ...value, snap: e.target.checked })}
        />
        Přichytávat k mřížce
      </label>
      <label className="field">
        Rozteč mřížky
        <select
          value={value.gridSize}
          onChange={(e) =>
            onChange({ ...value, gridSize: Number(e.target.value) })
          }
        >
          {[10, 20, 40].map((n) => (
            <option key={n} value={n}>
              {n} px
            </option>
          ))}
        </select>
      </label>
      <h3>Kreslení</h3>
      <label className="check">
        <input
          type="checkbox"
          checked={value.drawingGrid}
          onChange={(e) =>
            onChange({ ...value, drawingGrid: e.target.checked })
          }
        />
        Pomocná mřížka kreslení
      </label>
      <p className="muted">
        Excalidraw u této mřížky současně zapíná přichytávání.
      </p>
      <div className="removal-actions">
        <button onClick={onClose}>Hotovo</button>
      </div>
    </dialog>
  );
}
