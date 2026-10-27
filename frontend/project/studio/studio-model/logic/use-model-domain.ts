// Modelová doména, kterou MODEL právě ukazuje (docs/studio.md §4): výchozí je doména architektury ze zanoření, scénář
// z knihovny ji přepne na vlastní pojmenovanou doménu `scenario:<id>`. Když doména scénáře ještě nemá uložený model,
// naplní se scénářem jako neuložený obsah (Uložit ho zapíše); uložená verze se jen otevře a nikdy se nepřepíše.
// Návrat na doménu architektury nechá její model, jak byl uložen.
import { useEffect, useRef, useState } from "react";
import { materializeScenario, type Scenario } from "../../model/simulation/logic";
import { scenarioDomain, scenarioDomainName } from "../../studio-model-scenarios/logic/scenario-library";
import type { EditModel } from "./model-edit";

type Editor = { status: string; loadedDomain: string; revision: number; apply: (change: (model: EditModel) => EditModel) => void };

export function useModelDomain(domainId: string, domainName: string) {
  const [scenario, setScenario] = useState<Scenario | null>(null);
  return {
    id: scenario ? scenarioDomain(scenario.id) : domainId,
    name: scenario ? scenarioDomainName(scenario) : domainName,
    scenario, architecture: domainName,
    open: (next: Scenario) => setScenario(next),
    back: () => setScenario(null),
  };
}

/** Po načtení domény scénáře: prázdnou (nikdy neuloženou) naplní scénářem; `onSeed(fresh)` řekne, co se stalo. */
export function useScenarioSeed(editor: Editor, scenario: Scenario | null, key: string, onSeed: (fresh: boolean) => void) {
  const seeded = useRef<Scenario | null>(null);
  const { status, loadedDomain, revision, apply } = editor;
  useEffect(() => {
    if (!scenario || seeded.current === scenario || status !== "ready" || loadedDomain !== key) return;
    seeded.current = scenario;
    // Revize patří načtené verzi (model editoru může být v tomto snímku ještě předchozí doména): 0 = nikdy neuloženo.
    const fresh = revision === 0;
    if (fresh) apply(() => materializeScenario(scenario.id, key));
    onSeed(fresh);
  }, [scenario, status, loadedDomain, revision, key, apply, onSeed]);
}
