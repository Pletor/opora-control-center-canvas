import { EDGE_VIA, type EdgeVia, type FlowEdge } from "../logic/flow-types";

type Props = {
  edge: FlowEdge | undefined; message: string; frames: boolean; selection: number;
  onPalette: () => void; onRemoveEdge: () => void; onNote: () => void; onGroup: () => void;
  /** Jen s propem `frames`: rozložit uzly do pruhů vrstev a nastavit `via` vybrané hrany. */
  onLanes?: () => void; onVia?: (via: EdgeVia | undefined) => void;
};

/** Pás nástrojů nad plátnem: přidat uzel, u plátna toku přidat poznámku a rámec z výběru (Shift+tah nebo Ctrl+klik
 * vybere víc uzlů), odebrat vybranou vazbu a hláška, proč úprava nevznikla. */
export default function FlowToolbar({ edge, message, frames, selection, onPalette, onRemoveEdge, onNote, onGroup, onLanes, onVia }: Props) {
  return <div className="flow-editor__tools">
    <button type="button" className="flow-editor__tool" data-testid="flow-add-node" onClick={onPalette}>+ Uzel</button>
    {frames && <>
      <button type="button" className="flow-editor__tool" data-testid="flow-add-note" onClick={onNote}>+ Poznámka</button>
      <button type="button" className="flow-editor__tool" data-testid="flow-add-group" disabled={selection < 2}
        title={selection < 2 ? "Vyberte aspoň dva uzly (Shift + tah nebo Ctrl + klik)" : `Obalit ${selection} uzlů rámcem`} onClick={onGroup}>Rámec z výběru{selection > 1 ? ` (${selection})` : ""}</button>
      {onLanes && <button type="button" className="flow-editor__tool" data-testid="flow-arrange-lanes" title="Přeskládat uzly do pruhů FE, BE, DB, Infra, AI (mění jen svislou polohu)" onClick={onLanes}>Rozložit do pruhů</button>}
    </>}
    {edge && <span className="flow-editor__edge">vazba {edge.source_node}.{edge.source_port} → {edge.target_node}.{edge.target_port}
      {onVia && <select className="flow-editor__tool" aria-label="Přechod hrany (via)" data-testid="flow-edge-via" value={edge.via ?? ""}
        onChange={(event) => onVia((event.target.value || undefined) as EdgeVia | undefined)}>
        <option value="">via: —</option>{EDGE_VIA.map((via) => <option key={via} value={via}>via: {via}</option>)}</select>}
      <button type="button" className="flow-editor__tool" onClick={onRemoveEdge}>Odebrat vazbu</button></span>}
    {message && <span className="flow-editor__message" role="alert">{message}</span>}
  </div>;
}
