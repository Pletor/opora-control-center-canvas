/** Brána projektu je vypnutá: jeden řádek a tlačítko, které ji zapne (hlásí nahoru, zapíná rodič); pod tím případná chyba. */
export default function GateOff({ failure, onEnable }: { failure: string; onEnable: () => void }) {
  return (
    <div className="heart-channel__gate-off">
      <p className="heart-channel__gate-off-text">Brána projektu je vypnutá, srdce v něm nepracuje.</p>
      <button type="button" className="heart-channel__button" onClick={onEnable}>Zapnout bránu</button>
      {failure && <p role="alert" className="heart-channel__gate-off-error">Bránu se nepodařilo zapnout: {failure}</p>}
    </div>
  );
}
