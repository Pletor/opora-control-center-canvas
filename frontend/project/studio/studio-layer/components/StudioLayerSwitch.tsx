import type { StudioLayer } from "../logic/studio-layer";
import "../styles/studio-layer.css";

/** Přepínač vrstev v liště Studia: Skutečnost | MODEL. MODEL jde zapnout jen v doméně a pod ní (jinak je tlačítko
 * vypnuté s vysvětlením); volbu hlásí rodiči (`onChange`), adresu zapisuje rodič. */
export default function StudioLayerSwitch({ layer, modelAvailable, onChange }: { layer: StudioLayer; modelAvailable: boolean; onChange: (layer: StudioLayer) => void }) {
  return <div className="studio-layer" role="radiogroup" aria-label="Vrstva Studia" data-testid="studio-layer">
    <button type="button" role="radio" aria-checked={layer === "reality"} data-testid="studio-layer-reality"
      className={"studio-layer__option studio-layer__option--reality" + (layer === "reality" ? " studio-layer__option--on" : "")}
      title="Skutečnost: jen co v projektu opravdu je; nic se tu neukládá" onClick={() => onChange("reality")}>Skutečnost</button>
    <button type="button" role="radio" aria-checked={layer === "model"} data-testid="studio-layer-model" disabled={!modelAvailable}
      className={"studio-layer__option studio-layer__option--model" + (layer === "model" ? " studio-layer__option--on" : "")}
      title={modelAvailable ? "MODEL: technický model domény, výpočet, ne měření" : "MODEL je k dispozici v doméně: nejdřív do ní vstupte"}
      onClick={() => onChange("model")}>MODEL</button>
  </div>;
}
