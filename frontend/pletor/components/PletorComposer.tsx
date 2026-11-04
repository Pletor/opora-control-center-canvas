import { useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

type Props = { disabled: boolean; interim?: string; onSend: (text: string) => Promise<boolean>; children?: ReactNode };

/**
 * Pole pro zprávu a tlačítko Odeslat; Enter odešle, Shift+Enter dělá nový řádek. Text se smaže až po úspěchu.
 * Při poslechu pole ukazuje průběžný přepis (`interim`) jen ke čtení; odeslání věty řídí hlas sám.
 * `children` jsou ovladače hlasu od rodiče (mikrofon, přepínače) mezi polem a Odeslat.
 */
export default function PletorComposer({ disabled, interim = "", onSend, children }: Props) {
  const [text, setText] = useState("");
  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const value = text.trim();
    if (!value || disabled || interim) return;
    if (await onSend(value)) setText("");
  }
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) void submit(event);
  }
  return (
    <form className="pletor__composer" onSubmit={(event) => void submit(event)}>
      <textarea className="pletor__input" aria-label="Zpráva Pletorovi" rows={2} placeholder="Napiš Pletorovi, nebo klikni na mikrofon…"
        value={interim || text} readOnly={!!interim} onChange={(event) => setText(event.target.value)} onKeyDown={onKey} />
      {children}
      <button type="submit" className="pletor__send" disabled={disabled || !text.trim() || !!interim}>Odeslat</button>
    </form>
  );
}
