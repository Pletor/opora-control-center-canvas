// Horní pás Velínu: celé plátno jedním pohledem — pruh stavů a čtyři čísla, na která se člověk dívá nejdřív.
// Bez přehledu práce jsou „pracuje“ a „čeká na tebe“ neúplné; pás to řekne, místo aby ukázal falešný klid.
import type { Counts, WorkState } from "../logic/tower-model";
import TowerBar from "./TowerBar";

type Props = { counts: Counts; requests: number; requestCards: number; workState: WorkState };

export default function TowerSummary({ counts, requests, requestCards, workState }: Props) {
  const partial = workState !== "loaded";
  const facts: { key: string; value: string; label: string; title?: string; hot?: boolean }[] = [
    { key: "cards", value: String(counts.cards), label: "karty" },
    { key: "closed", value: String(counts.closed), label: "hotovo" },
    { key: "running", value: partial ? "?" : String(counts.running), label: "pracuje" },
    { key: "waiting", value: requests + (partial ? "+?" : ""), label: "čeká na tebe", hot: requests > 0,
      title: requests + " požadavků na " + requestCards + " kartách" },
  ];
  return (
    <header className={"tower-summary" + (partial ? " tower-summary--partial" : "")}>
      <h1 className="tower-summary__title">Velín</h1>
      <div className="tower-summary__bar">
        <TowerBar counts={counts} />
        {partial && <span className="tower-summary__partial">{workState === "loading" ? "načítám stav práce…" : "stav práce neúplný"}</span>}
      </div>
      <dl className="tower-summary__facts">
        {facts.map((f) => (
          <div key={f.key} className={"tower-summary__fact" + (f.hot ? " tower-summary__fact--hot" : "")} title={f.title}>
            <dt className="tower-summary__label">{f.label}</dt>
            <dd className="tower-summary__value">{f.value}</dd>
          </div>
        ))}
      </dl>
    </header>
  );
}
