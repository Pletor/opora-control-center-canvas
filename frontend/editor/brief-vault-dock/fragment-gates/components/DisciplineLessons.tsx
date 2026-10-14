// Poučení disciplíny fragmentu, jen zobrazení (docs/schranka-neurony.md §5, §9 bod 12): živá poučení nad prahem
// seřazená podle platné váhy, která vyhasíná s poločasem 30 dní od posledního potvrzení. Potvrzují a vyřazují
// je agenti a člověk přes API, ne odsud.
import { useVaultGet, type VaultScope } from "../../logic/vault-actions";
import { disciplineLabel } from "../../logic/disciplines";
import { shortWhen } from "../../logic/vault-dock-model";
import { whoLabel } from "../logic/gate-view";

type Lesson = { id: string; kind: "pattern" | "antipattern"; text: string; effectiveWeight: number; confirmedAt: string; by: string; actor: string };

export default function DisciplineLessons({ scope, discipline }: { scope: VaultScope; discipline: string }) {
  const { data, error } = useVaultGet<{ lessons: Lesson[]; halfLifeDays: number }>(
    "/api/brief-vault/lessons?" + new URLSearchParams({ ...scope, discipline }), discipline);
  const lessons = data?.lessons ?? [];
  return (
    <div className="fragment-gates__lessons" data-testid="discipline-lessons">
      <h5 className="fragment-gates__title">Poučení disciplíny {disciplineLabel(discipline)}</h5>
      {error && <p className="vault-dock__error" role="alert">Poučení nelze načíst: {error}</p>}
      {data && !lessons.length && <p className="vault-panel__text">Zatím žádné živé poučení. Vzniká branou 8. Poučení.</p>}
      {lessons.map((lesson) => (
        <div key={lesson.id} className="fragment-gates__lesson">
          <span className={"vault-tag" + (lesson.kind === "antipattern" ? " vault-tag--changed" : " vault-tag--mvp")}>{lesson.kind === "antipattern" ? "antivzor" : "vzor"}</span>
          <span className="fragment-gates__lesson-text">{lesson.text}</span>
          <span className="fragment-gates__weight" title={`Platná váha; poločas ${data?.halfLifeDays ?? 30} dní od posledního potvrzení (${shortWhen(lesson.confirmedAt)})`}>
            {Math.round(lesson.effectiveWeight * 100)} % · {whoLabel(lesson.by, lesson.actor)}</span>
        </div>
      ))}
    </div>
  );
}
