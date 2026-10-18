// Panel „Podklady“: nahoře nahrání obrázku a zpráva o chybě, pod tím karta každého podkladu s náhledem a pokynem
// pro agenta (účel, cíl, moment, barva, text). Dílek nic neukládá; nahrání, úpravy i smazání hlásí rodiči.
import { MAX_ASSETS, type AssetPurpose, type ColorUse, type StoryboardAsset } from "../logic/storyboard-model";

export default function AssetPanel({ assets, layers, moments, images, readOnly, busy, message, onUpload, onChange, onRemove }: {
  assets: StoryboardAsset[];
  layers: { id: string; label: string }[];
  moments: { id?: string; t: number; title: string }[];
  /** Načtené obrázky podle `fileId`; chybějící se teprve načítají. */
  images: ReadonlyMap<string, HTMLImageElement>;
  readOnly: boolean;
  busy: boolean;
  message: string;
  onUpload: (file: File) => void;
  onChange: (index: number, patch: Partial<StoryboardAsset>) => void;
  onRemove: (index: number) => void;
}) {
  const full = assets.length >= MAX_ASSETS;
  return (
    <section className="asset-panel" aria-label="Podklady">
      <div className="asset-panel__upload">
        <label className="asset-panel__field">Nahrát obrázek
          <input type="file" accept="image/png,image/jpeg,image/webp" disabled={readOnly || busy || full}
            onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) onUpload(file); }} />
        </label>
        {full && <p className="asset-panel__hint">Storyboard má nejvýše {MAX_ASSETS} podkladů.</p>}
        {message && <p className="asset-panel__message" role="alert">{message}</p>}
      </div>
      <ul className="asset-panel__list">
        {assets.map((asset, i) => {
          const n = i + 1;
          const image = images.get(asset.fileId);
          return (
            <li key={asset.id ?? `${asset.fileId}-${i}`} className={"asset-panel__item" + (asset.answered ? "" : " asset-panel__item--open")}>
              {image
                ? <img className="asset-panel__thumb" src={image.src} alt={asset.name} />
                : <div className="asset-panel__thumb asset-panel__thumb--loading">načítám…</div>}
              <div className="asset-panel__fields">
                <input type="text" value={asset.name} maxLength={120} disabled={readOnly} aria-label={`Název podkladu ${n}`}
                  onChange={(e) => onChange(i, { name: e.target.value })} />
                <select value={asset.purpose} disabled={readOnly} aria-label={`Účel podkladu ${n}`}
                  onChange={(e) => onChange(i, { purpose: e.target.value as AssetPurpose })}>
                  <option value="texture">Textura – agent ji kreslí</option>
                  <option value="reference">Reference – jen vzor</option>
                </select>
                <select value={asset.target} disabled={readOnly} aria-label={`Cíl podkladu ${n}`}
                  onChange={(e) => onChange(i, { target: e.target.value })}>
                  <option value="">Celá animace</option>
                  {layers.map((layer) => <option key={layer.id} value={layer.id}>{layer.label}</option>)}
                </select>
                <select value={asset.momentId} disabled={readOnly} aria-label={`Moment podkladu ${n}`}
                  onChange={(e) => onChange(i, { momentId: e.target.value })}>
                  <option value="">Všechny momenty</option>
                  {moments.filter((m) => m.id).map((m) => <option key={m.id} value={m.id}>{`${m.t} s · ${m.title}`}</option>)}
                </select>
                <div className="asset-panel__color">
                  <input type="color" value={asset.color || "#ffffff"} disabled={readOnly} aria-label={`Barva podkladu ${n}`}
                    onChange={(e) => onChange(i, asset.colorUse ? { color: e.target.value } : { color: e.target.value, colorUse: "object" })} />
                  <button type="button" disabled={readOnly || !asset.color} onClick={() => onChange(i, { color: "", colorUse: "" })}>bez barvy</button>
                  {asset.color && (
                    <select value={asset.colorUse} disabled={readOnly} aria-label={`Použití barvy podkladu ${n}`}
                      onChange={(e) => onChange(i, { colorUse: e.target.value as ColorUse })}>
                      {!asset.colorUse && <option value="">vyber použití</option>}
                      <option value="object">barva prvku</option>
                      <option value="tint">přebarvení textury</option>
                    </select>
                  )}
                </div>
                <textarea value={asset.note} maxLength={500} rows={2} disabled={readOnly} placeholder="Co s tím má agent udělat"
                  aria-label={`Pokyn k podkladu ${n}`} onChange={(e) => onChange(i, { note: e.target.value })} />
                <div className="asset-panel__foot">
                  <span className={"asset-panel__state" + (asset.answered ? " asset-panel__state--done" : "")}>{asset.answered ? "použito" : "čeká na agenta"}</span>
                  <button type="button" disabled={readOnly} aria-label={`Smazat podklad ${n}`} onClick={() => onRemove(i)}>Smazat</button>
                </div>
              </div>
            </li>
          );
        })}
        {assets.length === 0 && <li className="asset-panel__empty">Zatím bez podkladů. Nahraný obrázek agent použije jako texturu nebo vzor.</li>}
      </ul>
    </section>
  );
}
