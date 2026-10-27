// Výukové scénáře MODEL (prototyp `scenarios.mjs`): `materializeScenario` z definice scénáře postaví nový model S4.
// Scénář se otevírá jen jako nová pojmenovaná modelová doména (docs/studio.md §4), nikdy nepřepíše existující model.
// Materializovaný model nese `modelDefinition` s příznakem `layer: "MODEL"`: jde o výpočet, ne o skutečnost.
import { STUDIO_POLICY, TYPED_POLICY, type ConnectionPolicy } from "../../logic/connection-policy";
import { connect, createNode } from "../../logic/model-rules";
import { emptyStudioModel, type StudioModel } from "../../logic/model-types";
import { withSimulationDefaults } from "./model-adapter";
import { scenarios } from "./scenarios-data";
import { MODEL_VERSION } from "./simulation-config";
import type { ModelDefinition } from "./simulation-types";

export { scenarios, type Scenario } from "./scenarios-data";

export type MaterializedScenario = StudioModel & { modelDefinition: ModelDefinition };

/** Nový model domény `domainId` ze scénáře. ID uzlů jsou reference scénáře (`client`, `db`…), ID vazeb `edge-1…`,
 *  takže stejný scénář dává vždy stejný model. Scénáře bez pravidel Studia se propojují jen podle typů portů. */
export function materializeScenario(scenarioId: string, domainId = `model-${scenarioId}`): MaterializedScenario {
  const scenario = scenarios.find((s) => s.id === scenarioId);
  if (!scenario) throw new Error("Scénář neexistuje.");
  const policy: ConnectionPolicy = scenario.connectionPolicy === STUDIO_POLICY ? STUDIO_POLICY : TYPED_POLICY;
  const nodes = scenario.nodes.map((def, index) => {
    const node = withSimulationDefaults(createNode(def.type, { x: def.x, y: def.y }, def.ref), `${def.ref}:pods`);
    if (def.name) node.name = def.name;
    node.config = { ...node.config, model: { ...def.model } };
    // Kompaktní třísloupcové rozvržení ke studiu; pozice zůstávají po vložení volně upravitelné.
    if (scenario.id !== "deployment-scaling") node.position = { x: (index % 3) * 385, y: Math.floor(index / 3) * 350 + 60 };
    return node;
  });
  let model: StudioModel = { ...emptyStudioModel(domainId), nodes };
  scenario.edges.forEach((def, index) => {
    model = connect(model, { nodeId: def.a, portId: def.out }, { nodeId: def.b, portId: def.input }, policy, `edge-${index + 1}`).model;
  });
  const modelDefinition: ModelDefinition = {
    version: MODEL_VERSION, layer: "MODEL", scenarioId: scenario.id, name: `MODEL · ${scenario.name}`, principle: scenario.principle, limitations: scenario.limits,
    connectionPolicy: policy, incidents: (scenario.incidents || []).map((e) => ({ tick: e.tick, kind: e.kind, nodeIds: [...e.refs] })),
  };
  return { ...model, modelDefinition };
}
