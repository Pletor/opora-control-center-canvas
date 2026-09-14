import type { SurfaceSettings } from "@/shared/surface-settings/logic/workspace-settings";

/** Plátno: mřížka a přichytávání. Preference tohoto prohlížeče, nemění zadání ani soubory projektu. */
export default function CanvasSection({ value, onChange }: { value: SurfaceSettings; onChange: (value: SurfaceSettings) => void }) {
  return (
    <section className="settings-section" aria-labelledby="canvas-title">
      <h3 id="canvas-title">Plátno</h3>
      <p className="muted">Preference tohoto prohlížeče. Nemění zadání ani soubory projektu.</p>
      <h4>Struktura a mapa</h4>
      <label className="check">
        <input type="checkbox" checked={value.showGrid} onChange={(e) => onChange({ ...value, showGrid: e.target.checked })} />
        Zobrazit mřížku
      </label>
      <label className="check">
        <input type="checkbox" checked={value.snap} onChange={(e) => onChange({ ...value, snap: e.target.checked })} />
        Přichytávat k mřížce
      </label>
      <label className="field">
        Rozteč mřížky
        <select value={value.gridSize} onChange={(e) => onChange({ ...value, gridSize: Number(e.target.value) })}>
          {[10, 20, 40].map((n) => (
            <option key={n} value={n}>{n} px</option>
          ))}
        </select>
      </label>
      <h4>Kreslení</h4>
      <label className="check">
        <input type="checkbox" checked={value.drawingGrid} onChange={(e) => onChange({ ...value, drawingGrid: e.target.checked })} />
        Pomocná mřížka kreslení
      </label>
      <p className="muted">Excalidraw u této mřížky současně zapíná přichytávání.</p>
    </section>
  );
}
