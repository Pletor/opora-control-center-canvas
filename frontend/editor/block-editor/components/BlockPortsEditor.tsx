// Porty bloku v Editoru: na rozdíl od karty na plátně je tu dost místa, takže popisek je rovnou vidět
// jako vstup, ne skrytý za dvojklikem. Řádek se ukládá až po opuštění pole, ne po každém znaku.
import { useEffect, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import { MAX_BLOCK_PORT_LABEL, MAX_BLOCK_PORTS, type BlockPortDef } from "@/shared/desktop-state/logic/types";

function PortRow({
  port,
  disabled,
  onRename,
  onRemove,
}: {
  port: BlockPortDef;
  disabled: boolean;
  onRename: (label: string) => void;
  onRemove: () => void;
}) {
  const [label, setLabel] = useState(port.label);
  useScopedSaveParticipant({ id: `block-port:${port.id}`, label: `Popisek portu: ${port.label}`,
    dirty: label !== port.label, blocked: "Dokončete popisek portu a vyčkejte na jeho uložení." });
  useEffect(() => setLabel(port.label), [port.label]);
  return (
    <li className="block-editor__port">
      <input
        className="block-editor__port-input"
        aria-label={`Popisek portu ${port.label}`}
        value={label}
        disabled={disabled}
        maxLength={MAX_BLOCK_PORT_LABEL}
        onChange={(e) => setLabel(e.target.value)}
        onBlur={() => { if (label.trim() && label !== port.label) onRename(label.trim()); }}
        onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
      />
      <button type="button" className="block-editor__port-remove" aria-label={`Odebrat port ${port.label}`} disabled={disabled} onClick={onRemove}>✕</button>
    </li>
  );
}

export default function BlockPortsEditor({
  ports,
  disabled,
  onAdd,
  onRename,
  onRemove,
}: {
  ports: BlockPortDef[];
  disabled: boolean;
  onAdd: () => void;
  onRename: (portId: string, label: string) => void;
  onRemove: (portId: string) => void;
}) {
  return (
    <section className="block-editor__section" aria-label="Porty bloku">
      <h5>Porty</h5>
      {ports.length === 0 && <p className="block-editor__empty">Blok zatím nemá port. Z portu se na plátně táhne vazba na jinou kartu.</p>}
      <ul className="block-editor__ports">
        {ports.map((port) => (
          <PortRow key={port.id} port={port} disabled={disabled} onRename={(label) => onRename(port.id, label)} onRemove={() => onRemove(port.id)} />
        ))}
      </ul>
      <button type="button" className="block-editor__add" disabled={disabled || ports.length >= MAX_BLOCK_PORTS} onClick={onAdd}>+ Port</button>
    </section>
  );
}
