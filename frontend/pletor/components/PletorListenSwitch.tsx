import "../styles/pletor-listener.css";

type Props = { on: boolean; onChange: (on: boolean) => void; label?: string; title?: string; error?: string; tone?: "bar" | "dark" | "small" };

/**
 * Přepínač Poslech (true/false): zapnutý Pletor trvale poslouchá okolí a reaguje, vypnutý nereaguje vůbec.
 * Stojí v horní liště vedle tlačítka Pletor, v liště HUD a v popupu; hodnotu drží App. `error` (nepovolený
 * mikrofon) ukáže tooltip a tlumeně červený rámeček. Stejný dílek slouží i malému přepínači „jen na oslovení“.
 */
export default function PletorListenSwitch({ on, onChange, label = "Poslech", title, error, tone = "dark" }: Props) {
  const hint = error || title || (on ? "Pletor poslouchá okolí a reaguje (klik = vypnout)" : "Zapnout poslech: Pletor bude reagovat na hlas");
  return (
    <button type="button" role="switch" aria-checked={on} title={hint}
      className={`pletor-switch pletor-switch--${tone}` + (on ? " pletor-switch--on" : "") + (error ? " pletor-switch--error" : "")}
      onClick={() => onChange(!on)}>
      <span className="pletor-switch__track" aria-hidden="true"><span className="pletor-switch__thumb" /></span>
      {label}
    </button>
  );
}
