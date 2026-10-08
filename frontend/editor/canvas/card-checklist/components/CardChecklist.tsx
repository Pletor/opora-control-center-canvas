// Kontrolní pás pod hlavičkou karty: deset políček v pevném pořadí, barva + značka = stav.
// Tooltip políčka říká, co chybí a kam to zapsat (stejný `hint`, jaký dostane agent v briefu).
import { STATE_LABEL, STATE_MARK, type CheckItem } from "@/editor/canvas/card-checklist/logic/card-checklist";
import "@/editor/canvas/card-checklist/styles/card-checklist.css";

export default function CardChecklist({ items }: { items: CheckItem[] }) {
  const done = items.filter((i) => i.state === "yes").length;
  return (
    <div className="card-checklist" aria-label={`Kontrolní pás: ${done} z ${items.length}`}>
      {items.map((item) => (
        <span key={item.key} className={`card-checklist__cell card-checklist__cell--${item.state}`}
          title={`${item.label}: ${STATE_LABEL[item.state]}${item.hint ? " · " + item.hint : ""}`}>
          <b aria-hidden="true">{STATE_MARK[item.state]}</b>
          <small>{item.label}</small>
        </span>
      ))}
    </div>
  );
}
