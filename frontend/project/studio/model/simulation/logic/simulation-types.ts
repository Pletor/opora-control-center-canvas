// Typy simulace vrstvy MODEL (docs/studio.md §5): vstupní doména enginu, stav běhu a jeho řádky. Engine `flow-model/1`
// převzatý z prototypu je dynamický (každý kernel vrací vlastní tvar `technology`), proto řádky uzlů nesou otevřené
// pole `technology` a konfigurace je slovník čísel a výčtových textů. Výpočet je model, nikdy měření.
import type { StudioModelEdge, StudioModelNode } from "../../logic/model-types";

/** Parametry modelu jednoho uzlu po složení výchozích hodnot (`config(node)`): čísla a výčtové texty. */
export type ModelConfig = Record<string, any>;

/** Pravidlo parametru pro inspektor a validaci (`parameters` v prototypu). */
export type ParameterRule = { label: string; min?: number; max?: number; step?: number; enum?: readonly string[] };
export type ParameterTable = Record<string, ParameterRule>;

/** Plánovaný incident v definici modelu: v kroku `tick` se na `nodeIds` provede příkaz `kind`. */
export type IncidentKind = "crash" | "slow" | "restore";
export type ModelIncident = { tick: number; kind: IncidentKind; nodeIds: string[] };

/** Příkaz běhu (`modelCommand`); `surge` a `variation` se přepínají, `restore-all` obnoví vše. */
export type ModelCommandKind = "surge" | "slow" | "crash" | "restore" | "variation" | "restore-all";

/** Definice MODEL části domény (`domain.modelDefinition` v prototypu): scénář, princip, hranice a plán incidentů. */
export type ModelDefinition = {
  version: "flow-model/1";
  /** Příznak vrstvy: definice je vždy MODEL (výpočet), nikdy skutečnost. */
  layer: "MODEL";
  scenarioId?: string;
  name?: string;
  principle: string;
  limitations: string;
  connectionPolicy?: string;
  incidents: ModelIncident[];
};

/** Definice Kubernetes Deploymentu (šablona řízených Podů, `deployment/1`); v modelu S4 leží v `config.deployment`. */
export type DeploymentDefinition = {
  version: "deployment/1";
  templateId: string;
  minReplicas: number;
  maxReplicas: number;
  targetUtilization: number;
  downscaleTicks: number;
  replacementTicks: number;
  readinessTicks: number;
  podCapacity: number;
  podLatencyMs: number;
  podConcurrency: number;
  telemetryShare: number;
  podResilience?: Record<string, number>;
  outputOverrides?: Record<string, number>;
};

/** Uzel tak, jak ho čte engine: uzel S4 a k němu definice Deploymentu (jen u typu `kubernetes-deployment`). */
export type SimNode = StudioModelNode & { deployment?: DeploymentDefinition };
export type SimEdge = StudioModelEdge;
/** Doména enginu: uzly, hrany a volitelná definice MODEL části (plán incidentů). */
export type SimDomain = { nodes: SimNode[]; edges: SimEdge[]; modelDefinition?: ModelDefinition };

/** Řádek uzlu v jednom kroku. Pevná pole jsou společná všem typům, `technology` nese výstup kernelu. */
export type NodeRow = Record<string, any> & {
  nodeId: string;
  state: string;
  offered: number;
  processed: number;
  admitted: number;
  rejected: number;
  backlog: number;
  completed: number;
  latencyMs: number;
  utilization: number;
  pressurePct: number;
  dependencySuccess: number;
  outputs: Record<string, number>;
  inputAcceptance: Record<string, number>;
};

export type EdgeFlow = {
  offered: number;
  accepted: number;
  rejected: number;
  response: number;
  type: string;
  delayed: boolean;
  reason: string;
  dispatchTick?: number;
  nextOffered?: number;
  nextDispatchTick?: number;
  synchronous?: boolean;
  latencyMs?: number;
  slow?: boolean;
};

export type RunIncident = { kind: string; remaining: number };
export type SimEvent = { id: string; tick: number; at: string; nodeId: string; kind: string; message: string; source: "educational-model" };
export type Summary = { offered: number; completed: number; rejected: number; backlog: number; maxLatencyMs: number };

export type SimulationState = {
  version: "flow-model/1";
  engineVersion: "flow-rules/1.18.0";
  source: "educational-model";
  tick: number;
  nodes: Record<string, NodeRow>;
  edges: Record<string, EdgeFlow>;
  events: SimEvent[];
  samples: (Summary & { tick: number })[];
  incidents: Record<string, RunIncident>;
  surge: number;
  variation: boolean;
  warnings: string[];
  definitionPending: boolean;
  preview?: boolean;
  summary?: Summary;
  controllers?: Record<string, any>;
};
