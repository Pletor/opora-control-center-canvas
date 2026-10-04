import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { canExpand, fieldHeight, lengthNote, MESSAGE_LIMIT } from "../logic/composer-size";
import { composeMessage, isLongPaste, newBlock, withBlockText, type PastedBlock } from "../logic/pasted-blocks";
import { slashHints } from "../logic/slash-commands";
import type { AssistantScope } from "../logic/assistant-api";
import PastedBlocks from "./PastedBlocks";
import ScopeSwitch from "./ScopeSwitch";

/**
 * Pole pro zprávu. Text drží rodič (koncept per úkol), dílek ho jen zobrazuje a hlásí změny.
 * `Enter` odešle, `Shift+Enter` zalomí řádek, pole má aspoň tři řádky a roste s textem do 40 % výšky
 * panelu. Dlouhý text jde tlačítkem rozbalit na tři čtvrtiny panelu a zase sbalit (`Esc`). Během běhu
 * je vedle pole Stop. Když text začíná `/`, nabídne lomítkové příkazy. `label` je drobný popisek nad
 * textem (na celé ploše „Odpověď do úkolu „…““), aby bylo jasné, kam zpráva jde.
 * Dlouhé vložení (`isLongPaste`) nejde do pole, ale jako dlaždice nad něj; pole zůstane volné pro pokyn.
 * Tužka na dlaždici vrátí text do pole a pole rozbalí. Při odeslání se pokyn a dlaždice složí do jedné zprávy.
 * Pod polem je přepínač rozsahu `ScopeSwitch` (Výběr / Celý obraz); volbu drží rodič.
 */
export default function Composer({
  value,
  pasted,
  busy,
  disabled,
  focusKey,
  label,
  scope,
  selectedCount,
  onScope,
  onChange,
  onPastedChange,
  onSend,
  onStop,
}: {
  value: string;
  pasted: PastedBlock[];
  busy: boolean;
  disabled: boolean;
  focusKey: string;
  label?: string;
  scope: AssistantScope;
  selectedCount: number;
  onScope: (scope: AssistantScope) => void;
  onChange: (text: string) => void;
  onPastedChange: (blocks: PastedBlock[]) => void;
  /** `draft` je jen text pole (pro smazání konceptu), `message` celá zpráva i s dlaždicemi. */
  onSend: (message: string, draft: string, blockIds: string[]) => void;
  onStop: () => void;
}) {
  const field = useRef<HTMLTextAreaElement>(null);
  const [hidden, setHidden] = useState(false);
  const hints = hidden ? [] : slashHints(value);
  const [expanded, setExpanded] = useState(false);
  const [tall, setTall] = useState(false);
  const message = composeMessage(value, pasted);
  const note = lengthNote(message.length);
  const over = message.length > MESSAGE_LIMIT;

  // Šířka pole se mění se změnou velikosti panelu; výšku je pak potřeba změřit znovu.
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = field.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useLayoutEffect(() => {
    const el = field.current;
    if (!el) return;
    const panel = el.closest<HTMLElement>(".assistant-panel");
    const panelHeight = panel?.clientHeight ?? window.innerHeight;
    el.style.height = "auto";
    const size = fieldHeight(el.scrollHeight, panelHeight, expanded);
    el.style.height = `${size.height}px`;
    el.style.overflowY = size.scroll ? "auto" : "hidden";
    setTall(canExpand(el.scrollHeight, panelHeight, expanded));
  }, [value, width, expanded]);

  // Odeslaná (vyprázdněná) zpráva pole zase sbalí.
  useEffect(() => { if (!value) setExpanded(false); }, [value]);

  // Přepnutí úkolu vrátí fokus do pole, aby se dalo hned psát dál.
  useEffect(() => { if (!disabled) field.current?.focus({ preventScroll: true }); }, [focusKey, disabled]);

  function submit() {
    if (!message || busy || disabled || over) return;
    onSend(message, value.trim(), pasted.map((b) => b.id));
  }

  function editBlock(block: PastedBlock) {
    onPastedChange(pasted.filter((b) => b.id !== block.id));
    onChange(withBlockText(value, block));
    setExpanded(true);
    field.current?.focus();
  }

  return (
    <form className="assistant-panel__composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      {hints.length > 0 && (
        <ul className="assistant-panel__slash" aria-label="Lomítkové příkazy">
          {hints.map((c) => (
            <li key={c.name}>
              <button
                type="button"
                className="assistant-panel__slash-option"
                onClick={() => { onChange(c.name + " "); field.current?.focus(); }}
              >
                <span className="assistant-panel__slash-name">{c.name}</span>
                <span className="assistant-panel__slash-hint">{c.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="assistant-panel__field">
        <PastedBlocks blocks={pasted} onEdit={editBlock} onRemove={(id) => onPastedChange(pasted.filter((b) => b.id !== id))} />
        <label className="assistant-panel__field-text">
          {(label || note || tall) && (
            <span className="assistant-panel__field-bar">
              {label && <span className="assistant-panel__field-label">{label}</span>}
              {note && (
                <span className={`assistant-panel__field-count${note.over ? " assistant-panel__field-count--over" : ""}`} aria-live="polite">
                  {note.text}
                </span>
              )}
              {tall && (
                <button
                  type="button"
                  className="assistant-panel__field-toggle"
                  aria-expanded={expanded}
                  title={expanded ? "Sbalit pole (Esc)" : "Rozbalit pole na celé zadání"}
                  onClick={() => { setExpanded(!expanded); field.current?.focus(); }}
                >
                  {expanded ? "Sbalit" : "Rozbalit"}
                </button>
              )}
            </span>
          )}
          <textarea
            ref={field}
            className="assistant-panel__input"
            aria-label="Zpráva pro asistenta"
            rows={1}
            value={value}
            disabled={disabled}
            placeholder={disabled ? "Nejdřív založte úkol." : "Napište zprávu…  (Enter odešle, Shift+Enter nový řádek)"}
            onChange={(e) => { setHidden(false); onChange(e.target.value); }}
            onPaste={(e) => {
              const text = e.clipboardData.getData("text/plain");
              if (!isLongPaste(text)) return;
              e.preventDefault();
              onPastedChange([...pasted, newBlock(text)]);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape" && hints.length) { e.preventDefault(); setHidden(true); return; }
              if (e.key === "Escape" && expanded) { e.preventDefault(); setExpanded(false); return; }
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
            }}
          />
        </label>
        {busy ? (
          <button type="button" className="assistant-panel__stop" onClick={onStop} title="Ukončit běžící tah">
            <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor" /></svg>
            Stop
          </button>
        ) : (
          <button type="submit" className="assistant-panel__send" disabled={disabled || !message || over} aria-label="Odeslat zprávu" title={over ? "Zpráva je delší než limit" : "Odeslat (Enter)"}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        )}
      </div>
      <ScopeSwitch scope={scope} selectedCount={selectedCount} onScope={onScope} />
    </form>
  );
}
