import type { ReactNode } from "react";
import type { PanelSize } from "../logic/assistant-prefs";

const OPTIONS: { size: PanelSize; label: string; hint: string; icon: ReactNode }[] = [
  {
    size: "minimized",
    label: "Minimalizovat",
    hint: "Minimalizovat do lišty vpravo dole",
    icon: <path d="M5 17h14" />,
  },
  {
    size: "side",
    label: "Panel vpravo",
    hint: "Panel na pravé straně obrazovky",
    icon: (
      <>
        <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
        <path d="M13 4.5v15" />
      </>
    ),
  },
  {
    size: "full",
    label: "Celá plocha",
    hint: "Na celou plochu pod horní lištou",
    icon: (
      <>
        <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
        <path d="M9 4.5v15" />
      </>
    ),
  },
];

/** Přepínač tří velikostí panelu. Jen hlásí volbu; velikost drží a ukládá rodič. */
export default function SizeSwitch({ size, onSize }: { size: PanelSize; onSize: (size: PanelSize) => void }) {
  return (
    <div className="assistant-panel__sizes" role="group" aria-label="Velikost asistenta">
      {OPTIONS.map((o) => (
        <button
          key={o.size}
          type="button"
          className={"assistant-panel__size" + (o.size === size ? " assistant-panel__size--on" : "")}
          aria-label={o.label}
          aria-pressed={o.size === size}
          title={o.hint + (o.size === "minimized" ? " (Esc)" : "")}
          onClick={() => onSize(o.size)}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
            {o.icon}
          </svg>
        </button>
      ))}
    </div>
  );
}
