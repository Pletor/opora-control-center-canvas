import { LAYER_LABEL, type LayerId, type LayerState } from "../logic/linie-prefs";

type Zoom = { text: string; zoomIn: () => void; zoomOut: () => void; all: () => void; now: () => void; reset: () => void };
type Props = {
  mode: "editor" | "git"; onMode: (mode: "editor" | "git") => void;
  zoom: Zoom; layers: LayerState; sources: Record<LayerId, boolean>; onLayer: (id: LayerId, on: boolean) => void;
  form: "" | "row" | "work"; onForm: (form: "" | "row" | "work") => void;
};

/**
 * Lišta nad plátnem: Editor | Git graf, měřítko (− · šířka · + · Vše · Teď · ↻ Výchozí), Vrstvy a dva zápisy.
 * Vrstva bez zdroje v boardu jde zapnout, ale stojí šedě s „bez zdroje“, aby nikdo nečekal, že se něco ukáže.
 */
export default function LinieToolbar({ mode, onMode, zoom, layers, sources, onLayer, form, onForm }: Props) {
  const editor = mode === "editor";
  return (
    <div className="pletor-dashboard__linie-bar">
      <span className="pletor-dashboard__tools" role="group" aria-label="Pohled">
        <button type="button" className="pletor-dashboard__button" aria-pressed={editor} onClick={() => onMode("editor")}>Editor</button>
        <button type="button" className="pletor-dashboard__button" aria-pressed={!editor} onClick={() => onMode("git")}>Git graf</button>
      </span>
      {editor && (
        <span className="pletor-dashboard__tools" role="group" aria-label="Měřítko">
          <button type="button" className="pletor-dashboard__button" aria-label="Oddálit" onClick={zoom.zoomOut}>−</button>
          <span className="pletor-dashboard__linie-scale">{zoom.text}</span>
          <button type="button" className="pletor-dashboard__button" aria-label="Přiblížit" onClick={zoom.zoomIn}>+</button>
          <button type="button" className="pletor-dashboard__button" onClick={zoom.all}>Vše</button>
          <button type="button" className="pletor-dashboard__button" onClick={zoom.now}>Teď</button>
          <button type="button" className="pletor-dashboard__button" onClick={zoom.reset}>↻ Výchozí</button>
        </span>
      )}
      {editor && (
        <details className="pletor-dashboard__linie-layers">
          <summary className="pletor-dashboard__button">Vrstvy ▾</summary>
          <div className="pletor-dashboard__linie-layers-menu">
            <p className="pletor-dashboard__note">Vždy: větve, kuličky, souhrn, ověřené začlenění; u vybrané kuličky i její commity a plán.</p>
            {(Object.keys(LAYER_LABEL) as LayerId[]).map((id) => (
              <label key={id} className={`pletor-dashboard__linie-layer${sources[id] ? "" : " pletor-dashboard__linie-layer--nosource"}`}>
                <input type="checkbox" checked={layers[id]} onChange={(event) => onLayer(id, event.target.checked)} />
                {LAYER_LABEL[id]}{sources[id] ? "" : " · bez zdroje"}
              </label>
            ))}
          </div>
        </details>
      )}
      <span className="pletor-dashboard__tools">
        <button type="button" className="pletor-dashboard__button" aria-expanded={form === "row"} onClick={() => onForm(form === "row" ? "" : "row")}>+ Přidat řádek</button>
        <button type="button" className="pletor-dashboard__button" aria-expanded={form === "work"} onClick={() => onForm(form === "work" ? "" : "work")}>+ Nová kulička</button>
      </span>
      {editor && <span className="pletor-dashboard__linie-hint">kolečko = čas · Shift+kolečko = posun · tažení = ruka · ✎/F2 = přejmenovat · Esc zavře nejbližší</span>}
    </div>
  );
}
