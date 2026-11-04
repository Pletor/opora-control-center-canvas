/** Tlačítko Pletor v horní liště vedle Asistenta: jen hlásí kliknutí, otevřenost drží rodič. */
export default function PletorButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button type="button" className={"pletor__toggle" + (open ? " pletor__toggle--open" : "")} aria-pressed={open}
      title={open ? "Zavřít Pletora" : "Pletor: záměry a rozhodnutí nad srdcem"} onClick={onToggle}>
      Pletor
    </button>
  );
}
