// Bloky obsahu přímo v kartě: každý blok je rámeček s hlavou (číslo · název · stav · nástroje) a pod ní
// textarea s popisem, dole řada portů (CardBlockPorts). Přidat / posunout / přejmenovat / odebrat / upravit
// text bublá nahoru, dílek nic neukládá. Dvojklik na kartu dál vede do hloubky, proto řádky zastavují jen
// svůj vlastní dvojklik. Uzavřená karta má bloky jen ke čtení. Blok vybraný na plátně (`data-block-id`
// čte Board z kliknutí) má zvýrazněný rámeček, aby bylo jasné, který dílek právě edituje knihovna vlevo.
// Nástroje bloku a editory portů má jen vybraná karta; v oddálení (`detail="far"`) zůstane z bloku jen
// číslo, název a úchyty portů, pokud v něm není rozepsaný nebo zaměřený text (ani rozepsaný editor portu).
// Ukládá se jen při blur. Rozepsaný popis a název žijí i v `logic/block-drafts.ts`: plátno kreslí jen karty
// v obraze, takže karta, která odjede, se odmontuje bez blur; po návratu pole draft převezme (nic se neukládá
// při odmontování) a zámek ukládání o něm ví i mimo obraz (`retainOnUnmount` + `hasDrafts`).
import { useEffect, useMemo, useRef, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import { notifySaveParticipants } from "@/shared/hooks/logic/save-coordinator";
import { useAddedPulse } from "../logic/use-added-pulse";
import type { CardBlockRow } from "@/editor/canvas/node-card/logic/card-model";
import CardBlockPorts, { type CardPortHandlers } from "@/editor/canvas/node-card/components/CardBlockPorts";
import { blocksDetail, type CardDetail } from "@/editor/canvas/node-card/logic/card-lod";
import { clearDraft, draftKey, hasDrafts, readDraft, writeDraft } from "@/editor/canvas/node-card/logic/block-drafts";

export type CardBlockHandlers = CardPortHandlers & {
  add: () => void;
  move: (blockId: string, delta: -1 | 1) => void;
  remove: (blockId: string) => void;
  rename: (blockId: string, title: string) => void;
  text: (blockId: string, text: string) => void;
};

const STATUS_TITLE: Record<CardBlockRow["status"], string> = { open: "otevřený", met: "splněný", unmet: "nesplněný", blocked: "blokovaný" };

export default function CardBlocks({
  id,
  rows,
  disabled,
  handlers,
  selectedBlockId,
  selected = true,
  detail = "full",
}: {
  id: string;
  rows: CardBlockRow[];
  disabled: boolean;
  handlers: CardBlockHandlers;
  /** Blok právě vybraný na plátně; zvýrazní se, ať sedí knihovna k tomu, co je vidět. */
  selectedBlockId?: string;
  /** Vybraná karta: jen ta ukazuje nástroje bloku a editory portů. */
  selected?: boolean;
  /** Úroveň detailu karty (oddálené plátno = `far`). */
  detail?: CardDetail;
}) {
  // Rozepsaný název bloku z dřívějška (karta byla mimo obraz) znovu otevře editor, jen bez krádeže fokusu.
  const [editing, setEditing] = useState<string | null>(() =>
    rows.find((row) => readDraft(draftKey(id, row.id, "title"), row.title) !== undefined)?.id ?? null);
  const restored = useRef(editing);
  const added = useAddedPulse(rows.map(row => row.id));
  const root = useRef<HTMLDivElement>(null);
  const [, changed] = useState(0);
  const hasDraft = () => hasDrafts(id) || Array.from(root.current?.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input[data-save-blur], textarea[data-save-blur]") ?? [])
    .some((field) => field.value !== field.defaultValue);
  useScopedSaveParticipant({ id: `card-blocks:${id}`, label: "Bloky na plátně",
    dirty: hasDraft(), isDirty: hasDraft, retainOnUnmount: true,
    blocked: "Dokončete popis nebo název bloku na plátně a vyčkejte na jeho uložení." });
  // Otisk uložených hodnot jen při změně řádků, ne v každém renderu karty.
  const savedValues = useMemo(() => JSON.stringify(rows.map((row) => [row.id, row.title, row.text])), [rows]);
  useEffect(() => { notifySaveParticipants(); }, [savedValues]);
  // Rozepsané nebo zaměřené pole (i rozepsaný editor portu, `data-dirty`) drží bloky celé i v oddálení.
  const focused = !!root.current && root.current.contains(document.activeElement);
  const shown = blocksDetail(detail, hasDraft() || focused || !!root.current?.querySelector("[data-dirty]"));
  const tools = selected && !disabled;
  const commit = (blockId: string, title: string, current: string) => {
    setEditing(null);
    const value = title.trim();
    if (value && value !== current) handlers.rename(blockId, value);
    clearDraft(draftKey(id, blockId, "title"));
  };
  const cancel = (blockId: string) => {
    setEditing(null);
    clearDraft(draftKey(id, blockId, "title"));
  };
  return (
    <div ref={root} onInputCapture={event => {
      if ((event.target as HTMLElement).hasAttribute("data-save-blur")) changed(value => value + 1);
    }} className="node-card__blocks" data-testid={"card-blocks-" + id}>
      {rows.length > 0 && (
        <ol className="node-card__block-list">
          {rows.map((row, index) => (
            <li key={row.id} className={"node-card__block-item" + (added.includes(row.id) ? " node-card__added-pulse" : "")} data-block-id={row.id}>
              {shown === "far" ? (
                <div className={`node-card__block node-card__block--far node-card__block--${row.status}`} data-testid={"card-block-" + row.id}>
                  <div className="node-card__block-head">
                    <span className="node-card__block-number">{row.number}</span>
                    <span className="node-card__block-title">{row.title}</span>
                    <span className="node-card__block-status" title={STATUS_TITLE[row.status]} aria-label={STATUS_TITLE[row.status]} />
                  </div>
                  <CardBlockPorts nodeId={id} blockId={row.id} ports={row.ports} disabled={disabled} handlers={handlers} detail="far" />
                </div>
              ) : (
              <div
                className={`node-card__block node-card__block--${row.status}` + (selectedBlockId === row.id ? " node-card__block--selected" : "")}
                data-testid={"card-block-" + row.id}
              >
                <div className="node-card__block-head">
                  <span className="node-card__block-number">{row.number}</span>
                  {editing === row.id ? (
                    <input
                      className="nodrag node-card__block-title-input"
                      aria-label="Název bloku"
                      defaultValue={readDraft(draftKey(id, row.id, "title"), row.title) ?? row.title}
                      data-save-blur="true"
                      autoFocus={restored.current !== row.id}
                      maxLength={160}
                      onFocus={(e) => e.currentTarget.select()}
                      onKeyDown={(e) => {
                        e.stopPropagation();
                        if (e.key === "Enter") commit(row.id, e.currentTarget.value, row.title);
                        if (e.key === "Escape") cancel(row.id);
                      }}
                      onChange={(e) => writeDraft(draftKey(id, row.id, "title"), row.title, e.currentTarget.value)}
                      onBlur={(e) => commit(row.id, e.currentTarget.value, row.title)}
                    />
                  ) : (
                    <span
                      className="node-card__block-title"
                      title={disabled ? row.title : "Dvojklik přejmenuje blok"}
                      onDoubleClick={(e) => { e.stopPropagation(); if (!disabled) { restored.current = null; setEditing(row.id); } }}
                    >
                      {row.title}
                    </span>
                  )}
                  <span className="node-card__block-status" title={STATUS_TITLE[row.status]} aria-label={STATUS_TITLE[row.status]} />
                  {tools && <span className="node-card__block-tools nodrag">
                    <button type="button" className="node-card__block-tool" aria-label="Posunout blok výš" disabled={disabled || index === 0} onClick={() => handlers.move(row.id, -1)}>▲</button>
                    <button type="button" className="node-card__block-tool" aria-label="Posunout blok níž" disabled={disabled || index === rows.length - 1} onClick={() => handlers.move(row.id, 1)}>▼</button>
                    <button type="button" className="node-card__block-tool" aria-label="Odebrat blok" disabled={disabled} onClick={() => handlers.remove(row.id)}>✕</button>
                  </span>}
                </div>
                <textarea
                  className="node-card__block-text nodrag"
                  aria-label="Popis bloku"
                  placeholder="Co se má stát a jak to má vypadat…"
                  rows={5}
                  defaultValue={readDraft(draftKey(id, row.id, "text"), row.text) ?? row.text}
                  data-save-blur="true"
                  readOnly={disabled}
                  onKeyDown={(e) => e.stopPropagation()}
                  onDoubleClick={(e) => e.stopPropagation()}
                  onChange={(e) => writeDraft(draftKey(id, row.id, "text"), row.text, e.currentTarget.value)}
                  onBlur={(e) => {
                    const value = e.currentTarget.value;
                    if (value !== row.text) handlers.text(row.id, value);
                    clearDraft(draftKey(id, row.id, "text"));
                  }}
                />
                <CardBlockPorts nodeId={id} blockId={row.id} ports={row.ports} disabled={disabled} handlers={handlers} detail={selected ? "full" : "row"} />
              </div>
              )}
            </li>
          ))}
        </ol>
      )}
      {tools && (
        <button type="button" className="node-card__block-add nodrag" onClick={(e) => { e.stopPropagation(); handlers.add(); }} onDoubleClick={(e) => e.stopPropagation()}>
          + Blok
        </button>
      )}
    </div>
  );
}
