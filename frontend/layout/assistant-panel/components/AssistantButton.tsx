/** Tlačítko Asistent v pravém rohu horní lišty. Jen hlásí kliknutí; otevřený stav drží rodič. */
export default function AssistantButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={"assistant-button" + (open ? " assistant-button--open" : "")}
      aria-pressed={open}
      title="Asistent: chat s Claude Code nad tímto projektem"
      onClick={onToggle}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" />
      </svg>
      <span className="assistant-button__label">Asistent</span>
    </button>
  );
}
