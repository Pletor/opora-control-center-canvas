import { useState } from "react";

/** Pole pro zprávu: Enter odešle, Shift+Enter zalomí řádek, během běhu místo odeslání svítí Stop. */
export default function Composer({
  busy,
  disabled,
  onSend,
  onStop,
}: {
  busy: boolean;
  disabled: boolean;
  onSend: (text: string) => Promise<boolean>;
  onStop: () => void;
}) {
  const [text, setText] = useState("");
  // Text zmizí až po přijetí zprávy; odmítnutou zprávu nemusí uživatel psát znovu.
  async function submit() {
    const value = text.trim();
    if (!value || busy || disabled) return;
    if (await onSend(value)) setText((current) => (current.trim() === value ? "" : current));
  }
  return (
    <form className="assistant-panel__composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea
        className="assistant-panel__input"
        aria-label="Zpráva pro asistenta"
        rows={3}
        value={text}
        disabled={disabled}
        placeholder={disabled ? "Nejdřív založte session." : "Napište zprávu (Enter odešle, Shift+Enter nový řádek)"}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
        }}
      />
      <div className="assistant-panel__actions">
        {busy && <button type="button" className="assistant-panel__stop" onClick={onStop}>Stop</button>}
        <button type="submit" className="assistant-panel__send" disabled={busy || disabled || !text.trim()}>Odeslat</button>
      </div>
    </form>
  );
}
