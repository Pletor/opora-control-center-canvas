/**
 * Zpráva srdci: záměr, změna nebo otázka. Text drží rodič. `Enter` odešle, `Shift+Enter` zalomí řádek.
 * Pole zůstává povolené i když srdce pracuje; nová zpráva počká na další dávku.
 */
export default function HeartComposer({
  value,
  sending,
  onChange,
  onSend,
}: {
  value: string;
  sending: boolean;
  onChange: (text: string) => void;
  onSend: () => void;
}) {
  return (
    <form className="heart-channel__composer" onSubmit={(event) => { event.preventDefault(); onSend(); }}>
      <textarea
        className="heart-channel__field heart-channel__field--composer"
        rows={3}
        value={value}
        aria-label="Zpráva srdci"
        placeholder="Záměr, změna nebo otázka pro srdce…"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            onSend();
          }
        }}
      />
      <button type="submit" className="heart-channel__button" disabled={!value.trim() || sending}>Poslat srdci</button>
    </form>
  );
}
