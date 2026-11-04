import "../styles/pletor-listener.css";

type Props = { on: boolean; onChange: (on: boolean) => void; label?: string; title?: string; error?: string; tone?: "bar" | "dark" | "small" };

/**
 * Přepínač Poslech (true/false): zapnutý Pletor trvale poslouchá okolí a reaguje, vypnutý nereaguje vůbec.
 * Stojí v horní liště vedle tlačítka Pletor, v liště HUD a v popupu; hodnotu drží App. Bez textu: ikona mikrofonu
 * a posuvník, stav nese barva; jméno „Poslech“ má čtečka (`aria-label`) i tooltip. `error` (nepovolený mikrofon)
 * ukáže tooltip a tlumeně červený rámeček. S `label` je to obyčejný přepínač s textem (volby v nastavení Pletora).
 */
export default function PletorListenSwitch({ on, onChange, label, title, error, tone = "dark" }: Props) {
  const hint = error || title || (on ? "Poslech: Pletor poslouchá okolí a reaguje (klik = vypnout)" : "Poslech: zapnout, Pletor bude reagovat na hlas");
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label ?? "Poslech"} title={hint}
      className={`pletor-switch pletor-switch--${tone}` + (on ? " pletor-switch--on" : "") + (error ? " pletor-switch--error" : "")}
      onClick={() => onChange(!on)}>
      {!label && (
        <svg className="pletor-switch__icon" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
        </svg>
      )}
      <span className="pletor-switch__track" aria-hidden="true"><span className="pletor-switch__thumb" /></span>
      {label}
    </button>
  );
}
