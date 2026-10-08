// Tělo karty: název (s přejmenováním přímo na kartě) a podstata do tří řádků.
// Přejmenování probublává nahoru přes onCommit / onCancel / onStart; stav „edituje se“ drží rodič.
import { useEffect, useRef, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";

export type RenameHandlers = { editing: boolean; start: () => void; cancel: () => void; commit: (name: string) => void };

export default function CardBody({ id, name, purpose, rename }: { id: string; name: string; purpose: string; rename?: RenameHandlers }) {
  const field = useRef<HTMLInputElement>(null);
  const [, changed] = useState(0);
  const dirty = () => !!rename?.editing && !!field.current && field.current.value !== name;
  useScopedSaveParticipant({ id: `card-name:${id}`, label: `Název uzlu: ${name}`,
    dirty: dirty(), isDirty: dirty, blocked: "Dokončete přejmenování karty a vyčkejte na uložení." });
  // React Flow kartu do změření skrývá, proto se fokus zkouší i v dalších snímcích.
  useEffect(() => {
    if (!rename?.editing) return;
    let frame = 0;
    let attempts = 0;
    const take = () => {
      if (field.current && document.activeElement !== field.current) {
        field.current.focus();
        field.current.select();
      }
      attempts += 1;
      if (field.current && document.activeElement !== field.current && attempts < 20) frame = requestAnimationFrame(take);
    };
    take();
    return () => cancelAnimationFrame(frame);
  }, [rename?.editing]);
  return (
    <div className="node-card__body">
      {rename?.editing ? (
        <h3 className="node-card__title">
          <input
            ref={field}
            className="nodrag node-card__rename"
            aria-label="Jméno uzlu na plátně"
            data-testid={"card-rename-" + id}
            defaultValue={name}
            onInput={() => changed((value) => value + 1)}
            autoFocus
            maxLength={160}
            onFocus={(e) => e.currentTarget.select()}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.nativeEvent.isComposing) return;
              if (e.key === "Enter") rename.commit(e.currentTarget.value);
              if (e.key === "Escape") rename.cancel();
            }}
            onBlur={(e) => rename.commit(e.currentTarget.value)}
          />
        </h3>
      ) : (
        <h3
          className="node-card__title"
          title="Dvojklik přejmenuje přímo na plátně"
          onDoubleClick={(e) => {
            e.stopPropagation();
            rename?.start();
          }}
        >
          {name}
        </h3>
      )}
      <p className={"node-card__purpose" + (purpose ? "" : " node-card__purpose--empty")}>{purpose || "Podstata zatím není popsána."}</p>
    </div>
  );
}
