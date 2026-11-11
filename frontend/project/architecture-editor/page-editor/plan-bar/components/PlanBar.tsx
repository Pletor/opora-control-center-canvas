import type { NextStep } from "../../logic/plan-progress";
import "../styles/plan-bar.css";

function stepText(next: NextStep): { title: string; note: string } {
  if (next.kind === "step") return { title: `Doplnit ${next.node.name}`, note: next.node.purpose || "Vstupy prvku jsou připravené." };
  if (next.kind === "verified") return { title: "Vše ověřeno", note: "Všechny prvky stránky prošly ověřením." };
  if (next.kind === "waiting") return { title: `Čeká na vstup: ${next.inputs.join(", ")}`, note: `${next.node.name} začne, až budou vstupy aspoň hotové.` };
  return { title: "Zatím žádný prvek", note: "Ve vrstvě 2 Logika vložte první prvek z palety vlevo." };
}

/** Pruh pod plátnem: další přípustný krok mezi prvky logiky s „Otevřít v Editoru →“. Nic neukládá. */
export default function PlanBar({ next, onOpenEditor }: { next: NextStep; onOpenEditor: (id: string) => void }) {
  const text = stepText(next);
  return <footer className="plan-bar" data-testid="architecture-next-step">
    <strong className="plan-bar__kicker">Další přípustný krok</strong>
    <div className="plan-bar__step">
      <span className="plan-bar__title">{text.title}</span>
      <span className="plan-bar__note">{text.note}</span>
    </div>
    {next.kind === "step" && <button type="button" className="plan-bar__open" data-testid="architecture-next-open" onClick={() => onOpenEditor(next.node.id)}>Otevřít v Editoru →</button>}
  </footer>;
}
