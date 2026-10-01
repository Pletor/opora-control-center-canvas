import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { slashHints } from "../logic/slash-commands";

/**
 * Pole pro zprávu. Text drží rodič (koncept per úkol), dílek ho jen zobrazuje a hlásí změny.
 * `Enter` odešle, `Shift+Enter` zalomí řádek, pole roste s textem do 40 % výšky panelu. Během běhu
 * je vedle pole Stop. Když text začíná `/`, nabídne lomítkové příkazy.
 */
export default function Composer({
  value,
  busy,
  disabled,
  focusKey,
  onChange,
  onSend,
  onStop,
}: {
  value: string;
  busy: boolean;
  disabled: boolean;
  focusKey: string;
  onChange: (text: string) => void;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const field = useRef<HTMLTextAreaElement>(null);
  const [hidden, setHidden] = useState(false);
  const hints = hidden ? [] : slashHints(value);

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
    const max = Math.max(120, (panel?.clientHeight ?? window.innerHeight) * 0.4);
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight + 2, max)}px`;
    el.style.overflowY = el.scrollHeight + 2 > max ? "auto" : "hidden";
  }, [value, width]);

  // Přepnutí úkolu vrátí fokus do pole, aby se dalo hned psát dál.
  useEffect(() => { if (!disabled) field.current?.focus({ preventScroll: true }); }, [focusKey, disabled]);

  function submit() {
    const text = value.trim();
    if (!text || busy || disabled) return;
    onSend(text);
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
        <textarea
          ref={field}
          className="assistant-panel__input"
          aria-label="Zpráva pro asistenta"
          rows={1}
          value={value}
          disabled={disabled}
          placeholder={disabled ? "Nejdřív založte úkol." : "Napište zprávu…  (Enter odešle, Shift+Enter nový řádek)"}
          onChange={(e) => { setHidden(false); onChange(e.target.value); }}
          onKeyDown={(e) => {
            if (e.key === "Escape" && hints.length) { e.preventDefault(); setHidden(true); return; }
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
          }}
        />
        {busy ? (
          <button type="button" className="assistant-panel__stop" onClick={onStop} title="Ukončit běžící tah">
            <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor" /></svg>
            Stop
          </button>
        ) : (
          <button type="submit" className="assistant-panel__send" disabled={disabled || !value.trim()} aria-label="Odeslat zprávu" title="Odeslat (Enter)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        )}
      </div>
    </form>
  );
}
