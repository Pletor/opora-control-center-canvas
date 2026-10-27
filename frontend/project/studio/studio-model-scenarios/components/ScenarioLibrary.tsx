import { useEffect, useMemo, useState } from "react";
import { scenarios, type Scenario } from "../../model/simulation/logic";
import { ALL_CATEGORIES, filterScenarios, scenarioCategories } from "../logic/scenario-library";
import "../styles/studio-model-scenarios.css";

/** Knihovna výukových scénářů nad plátnem MODELu (prototyp „Knihovna scénářů“): hledání, kategorie, karty scénářů
 * s pravidly a omezeními a „Otevřít v nové modelové doméně“. Otevření hlásí rodiči; stávající model zůstane, jak je.
 * Escape nebo × knihovnu zavře. */
export default function ScenarioLibrary({ onOpen, onClose }: { onOpen: (scenario: Scenario) => void; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState(ALL_CATEGORIES);
  const categories = useMemo(() => scenarioCategories(scenarios), []);
  const shown = useMemo(() => filterScenarios(scenarios, query, category), [query, category]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);
  return <section className="studio-model-scenarios" role="dialog" aria-modal="true" aria-label="Knihovna scénářů" data-testid="studio-model-scenario-library">
    <header className="studio-model-scenarios__head">
      <h2 className="studio-model-scenarios__title">Knihovna scénářů</h2>
      <button type="button" className="studio-model-scenarios__close" onClick={onClose} aria-label="Zavřít knihovnu">×</button>
    </header>
    <p className="studio-model-scenarios__notice">Vlastní vysvětlující modely založené na publikovaných pravidlech. Žádný scénář nepředstírá reálné nasazení
      ani přesnou simulaci konkrétní technologie. Otevření vytvoří novou modelovou doménu; model domény architektury zůstane beze změny.</p>
    <div className="studio-model-scenarios__filters">
      <input className="studio-model-scenarios__input" type="search" placeholder="Hledat scénáře" aria-label="Hledat scénáře" value={query} autoFocus
        data-testid="studio-model-scenario-search" onChange={(event) => setQuery(event.target.value)}/>
      <select className="studio-model-scenarios__input" value={category} aria-label="Kategorie scénáře" onChange={(event) => setCategory(event.target.value)}>
        {categories.map((item) => <option key={item}>{item}</option>)}
      </select>
      <small className="studio-model-scenarios__count">{shown.length} / {scenarios.length}</small>
    </div>
    <div className="studio-model-scenarios__grid">
      {shown.map((scenario) => <article key={scenario.id} className="studio-model-scenarios__card" data-testid={"studio-model-scenario-" + scenario.id}>
        <span className="studio-model-scenarios__pill">{scenario.category} · {scenario.nodes.length} komponent</span>
        <h3 className="studio-model-scenarios__name">{scenario.name}</h3>
        <p className="studio-model-scenarios__text">{scenario.description}</p>
        <details className="studio-model-scenarios__details"><summary>Pravidla a omezení</summary>
          <p className="studio-model-scenarios__text">{scenario.principle}</p><p className="studio-model-scenarios__text studio-model-scenarios__text--muted">{scenario.limits}</p>
        </details>
        <button type="button" className="studio-model-scenarios__open" data-testid={"studio-model-scenario-open-" + scenario.id} onClick={() => onOpen(scenario)}>Otevřít v nové modelové doméně</button>
      </article>)}
      {!shown.length && <p className="studio-model-scenarios__text">Žádný scénář neodpovídá hledání.</p>}
    </div>
  </section>;
}
