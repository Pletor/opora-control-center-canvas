/** Tlačítko Pletor v horní liště vedle Asistenta: hlásí klik (a zda se Shiftem), režim drží rodič. */
export default function PletorButton({ open, onToggle }: { open: boolean; onToggle: (fullscreen: boolean) => void }) {
  return (
    <button type="button" className={"pletor__toggle" + (open ? " pletor__toggle--open" : "")} aria-pressed={open}
      title={open ? "Pletor přes celou obrazovku" : "Pletor: záměry a rozhodnutí nad srdcem (Shift = plná obrazovka)"}
      onClick={(event) => onToggle(event.shiftKey)}>
      Pletor
    </button>
  );
}
