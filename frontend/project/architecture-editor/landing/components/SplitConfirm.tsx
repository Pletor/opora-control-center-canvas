import { useEffect, useRef } from "react";

/** Confirmation that moves one host of a legacy shared application into its own empty map. */
export default function SplitConfirm({ host, error, disabled, onConfirm, onCancel }: {
  host: string; error: string; disabled: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  const box = useRef<HTMLElement>(null);
  useEffect(() => {
    box.current?.scrollIntoView({ block: "nearest" });
    box.current?.querySelector<HTMLButtonElement>("button")?.focus({ preventScroll: true });
  }, []);
  return <section ref={box} className="ae-product-form arch-landing__split" role="region" aria-label="Oddělení domény">
    <h3>Oddělit {host}?</h3>
    <p>Vznikne nová prázdná mapa s vlastním ID. Všechny současné stránky a jejich zadání zůstanou v původní aplikaci. Host se přesune k nové doméně.</p>
    {error && <p role="alert">{error}</p>}
    <div className="ae-row">
      <button disabled={disabled} data-testid="architecture-confirm-split" onClick={onConfirm}>Oddělit do prázdné mapy</button>
      <button disabled={disabled} onClick={onCancel}>Zrušit</button>
    </div>
  </section>;
}
