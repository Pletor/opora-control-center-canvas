# Studio · MODEL · simulace

Engine simulace vrstvy **MODEL** (kontrakt `docs/studio.md` §5, etapa S5): čistý TypeScript bez UI, převedený téměř
1:1 z vlastního prototypu `04.Architektura-projektu/prototype` (`flow-model/1`, `flow-rules/1.18.0`; nic z `vendor/`).
Jeden krok = jedna modelová sekunda, deterministický, bez náhody. Výpočet je model, ne měření, a nikdy se nepíše do
karet OPORY. Celá složka se načítá líně (`await import(".../model/simulation/logic")`, vstup `logic/index.ts`); mimo
`model/` ji zatím nic neimportuje.

## Vstup: model S4 a adaptér (`logic/model-adapter.ts`)

Engine bere `SimulationModel` = `nodes` + `edges` modelu `opora.studio-model/1` a volitelné `modelDefinition`.
Tenký adaptér `simulationDomain(model)` vyrovná rozdíly proti doméně prototypu:

- parametry simulace jsou v `node.config.model`, ruční přepisy výstupů v `node.config.outputOverrides` (stejně jako v prototypu);
- definice šablony Podů (`deployment/1`) je v `node.config.deployment` a čte se jen u typu `kubernetes-deployment`
  (uzel S4 nemá `deployment`); Deployment bez ní škáluje podle staršího pravidla využití, jako v prototypu;
- řízený Pod (`type: "pod"` s `parentId`) do výpočtu nevstupuje, zastupují ho instance controlleru;
- `contracts`, `lifecycle`, `implementation` engine nepotřebuje;
- `modelDefinition` (`{version, layer: "MODEL", scenarioId?, name?, principle, limitations, connectionPolicy?, incidents}`)
  nese plán incidentů `{tick, kind: crash|slow|restore, nodeIds}`.

Adaptér nekopíruje `config`, změna parametru v modelu se projeví dalším krokem. `createSimulationNode` /
`withSimulationDefaults` doplní výchozí simulační konfiguraci jako prototypový `createNode` (Deployment: šablona Podů
a `crashAfterTicks: 3`, Service: `telemetryRate: 0.01`).

## Moduly (`logic/`)

| Prototyp | TS |
|---|---|
| `simulation.mjs` | `simulation.ts` (`createSimulation`, `stepSimulation`, `previewSimulation`, `modelCommand`, `rebaseSimulation`), `simulation-config.ts` (`config`, `parameters`, `parameterKeys`, `resilienceStep`, `validateModelConfig`), krok rozdělený na `step-schedule.ts`, `step-forward.ts` (+ `step-node-prepare.ts`, `step-node-behaviour.ts`, `step-node-outputs.ts`), `step-backward.ts`, `step-summary.ts` |
| `cache-model`, `pool-model`, `object-store-model`, `partitioned-model`, `serverless-model`, `gateway-model`, `monitoring-model`, `workflow-model` | stejná jména `.ts`; společná kontrola parametrů `parameter-check.ts` |
| `workflow-routing`, `cache-settlement`, `client-policy`, `cloud-profiles` | stejná jména `.ts` |
| `deployment.mjs` | `deployment-definition.ts` (šablona, validace, zdraví Podu) + `deployment.ts` (controller) |
| `technology.mjs` (výpočty) | `technology.ts`; data a meze jsou v S4 `model/logic/catalog-technology.ts` |
| `scenarios.mjs` | `scenarios-data.ts` (data, 47 scénářů) + `scenarios.ts` (`materializeScenario`) |
| `model.mjs` `validateDomain` (simulační část) | `simulation-validate.ts` (`validateSimulationModel`) |
| — | `simulation-types.ts`, `model-adapter.ts`, `index.ts` |

`materializeScenario(id, domainId?)` vrací nový model S4 s `modelDefinition.layer = "MODEL"`; ID uzlů jsou reference
scénáře, ID vazeb `edge-1…`. Scénáře bez pravidel Studia se propojují pravidly `typed-ports/1` (uloženo v
`modelDefinition.connectionPolicy`, `validateSimulationModel` ho použije).

## Testy

`logic/*.test.ts` (`npm test`): převedené testy prototypu `test/*.test.mjs` o simulaci a kernelech a
`simulation-reference.test.ts` (determinismus dvou běhů a referenční čísla prototypu pro web + DB, frontu + worker,
cache-aside, AI gateway a breaker s plánovanými incidenty).
