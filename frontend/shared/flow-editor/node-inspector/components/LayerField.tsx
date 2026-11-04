import { LAYERS, type Layer } from "../../logic/flow-types";
import { LAYER_LABEL } from "../../flow-lanes/logic/layers";

type Props = { value: Layer | undefined; typeLayer: Layer | undefined; readOnly: boolean; onLayer: (layer: Layer | undefined) => void };

/** Vrstva uzlu: výchozí je z typu, výběr jiné ji přepíše (výpočet smí běžet ve FE i v BE); „z typu“ přepis odebere. Typ bez vrstvy (krok na míru) ji musí mít na uzlu. */
export default function LayerField({ value, typeLayer, readOnly, onLayer }: Props) {
  return <label className="node-inspector__layer">
    <span className="node-inspector__key">Vrstva</span>
    <select className="node-inspector__input" disabled={readOnly} data-testid="node-layer" value={value ?? ""} onChange={(event) => onLayer((event.target.value || undefined) as Layer | undefined)}>
      {typeLayer && <option value="">z typu ({LAYER_LABEL[typeLayer]})</option>}
      {LAYERS.map((layer) => <option key={layer} value={layer}>{LAYER_LABEL[layer]}</option>)}
    </select>
  </label>;
}
