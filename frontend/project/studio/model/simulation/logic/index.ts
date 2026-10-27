// Veřejné rozhraní simulace vrstvy MODEL pro líné načtení: `const sim = await import(".../model/simulation/logic")`.
// Nic mimo `model/` tuto složku zatím staticky neimportuje (docs/studio.md §6: bundle MODEL se načítá líně).
export { createSimulation, modelCommand, previewSimulation, rebaseSimulation, stepSimulation } from "./simulation";
export { config, defaults, ENGINE_VERSION, MODEL_VERSION, parameterKeys, parameters, resilienceDefaults, resilienceKeys, resilienceStep, validateModelConfig } from "./simulation-config";
export { createSimulationNode, deploymentOf, isManagedPod, simulationDomain, withSimulationDefaults, type SimulationModel } from "./model-adapter";
export { controllerCommand, controllerCounts, controllerFaults, deploymentDefinition, deploymentFields, podResilienceFields, validateDeployment } from "./deployment";
export { materializeScenario, scenarios, type MaterializedScenario, type Scenario } from "./scenarios";
export { validateSimulationModel } from "./simulation-validate";
export type * from "./simulation-types";
