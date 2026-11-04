import { useState, type FormEvent, type KeyboardEvent } from "react";

/** Pole pro zprávu a tlačítko Odeslat; Enter odešle, Shift+Enter dělá nový řádek. Text se smaže až po úspěchu. */
export default function PletorComposer({ disabled, onSend }: { disabled: boolean; onSend: (text: string) => Promise<boolean> }) {
  const [text, setText] = useState("");
  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const value = text.trim();
    if (!value || disabled) return;
    if (await onSend(value)) setText("");
  }
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) void submit(event);
  }
  return (
    <form className="pletor__composer" onSubmit={(event) => void submit(event)}>
      <textarea className="pletor__input" aria-label="Zpráva Pletorovi" rows={2} placeholder="Napiš Pletorovi…"
        value={text} onChange={(event) => setText(event.target.value)} onKeyDown={onKey} />
      <button type="submit" className="pletor__send" disabled={disabled || !text.trim()}>Odeslat</button>
    </form>
  );
}
