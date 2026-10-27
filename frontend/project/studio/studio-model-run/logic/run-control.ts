// Řízení běhu MODELu (docs/studio.md §5, prototyp `app.mjs` `start` / `advanceModel` / `applyModelCommand`): stav běhu
// je stav enginu, zda běží, rychlost a krátká historie telemetrie. Tick = jedna modelová sekunda; při rychlosti 1× trvá
// na obrazovce 1 s, při 5× 200 ms. Krok počítá engine nad aktuálním (i neuloženým) modelem; incident se do běhu
// promítne hned přepočtem bez posunu času (náhled enginu), takže čítač ticku zůstává poctivý. Chyba výpočtu běh
// zastaví a řekne proč. Čistá logika bez Reactu; nic neukládá.
import { createSimulation, modelCommand, previewSimulation, stepSimulation } from "../../model/simulation/logic";
import type { ModelCommandKind, SimulationState } from "../../model/simulation/logic";
import type { EditModel } from "../../studio-model/logic/model-edit";
import { emptyHistory, recordTick, type RunHistory } from "./run-history";

export const RUN_SPEEDS = [0.25, 0.5, 1, 2, 5] as const;
export const DEFAULT_SPEED = 1;

export type RunState = { sim: SimulationState; running: boolean; speed: number; history: RunHistory; error: string };

export const clampSpeed = (speed: number) => Math.min(5, Math.max(0.25, Number.isFinite(speed) ? speed : DEFAULT_SPEED));
/** Prodleva mezi ticky na obrazovce: jedna modelová sekunda dělená rychlostí. */
export const tickDelayMs = (speed: number) => 1000 / clampSpeed(speed);

export const initialRun = (speed = DEFAULT_SPEED): RunState =>
  ({ sim: createSimulation(), running: false, speed: clampSpeed(speed), history: emptyHistory(), error: "" });

const message = (error: unknown) => error instanceof Error ? error.message : String(error);

/** Jeden tick: krok enginu a zápis do historie. Chyba výpočtu běh zastaví a stav nechá, jak byl. */
export function advanceRun(model: EditModel, run: RunState): RunState {
  try {
    const sim = stepSimulation(model, run.sim);
    return { ...run, sim, history: recordTick(run.history, sim), error: "" };
  } catch (error) {
    return { ...run, running: false, error: `Model nejde spočítat: ${message(error)}` };
  }
}

/** Incident nebo přepnutí zátěže hned do běhu: příkaz enginu a přepočet aktuálního ticku bez posunu času. */
export function commandRun(model: EditModel, run: RunState, kind: ModelCommandKind, nodeIds: readonly string[] = []): RunState {
  try {
    const sim = structuredClone(run.sim);
    modelCommand(sim, model, kind, nodeIds);
    return { ...run, sim: previewSimulation(model, sim), error: "" };
  } catch (error) {
    return { ...run, error: `Incident nejde použít: ${message(error)}` };
  }
}

/** Reset odstraní jen dočasný běh (stav, historii, incidenty běhu), definici modelu nechá; rychlost zůstane. */
export const resetRun = (run: RunState): RunState => initialRun(run.speed);

/** Běh, který už něco spočítal nebo nese incident (reset po změně modelu má smysl ohlásit). */
export const runTouched = (run: RunState) => run.running || run.sim.tick > 0 || Object.keys(run.sim.incidents).length > 0 || run.sim.surge !== 1;

/** Otisk toho, co počítá engine: typy, konfigurace a vazby (bez polohy a názvu karet a bez plánu incidentů, který se
 *  čte z aktuálního modelu v každém kroku). Změna otisku za běhu běh zastaví a vynuluje. */
export function runSignature(model: EditModel): string {
  return JSON.stringify([
    model.domainId,
    model.nodes.map((node) => [node.id, node.type, node.parentId ?? null, node.config]),
    model.edges.map((edge) => [edge.id, edge.from, edge.to, edge.type, edge.enabled, edge.condition ?? null]),
    model.modelDefinition?.connectionPolicy ?? null,
  ]);
}

/** Uzly s aktivním incidentem nebo automatickým selháním (pro „Obnovit vše“). */
export function incidentNodes(sim: SimulationState): string[] {
  return [...new Set([...Object.keys(sim.incidents), ...Object.values(sim.nodes).filter((row) => row.autoFailed).map((row) => row.nodeId)])];
}
