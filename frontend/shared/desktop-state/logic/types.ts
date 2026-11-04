// Typy pro Desktop v3 panely. Přesně dle CONTRACT.md; žádná demo/dummy data.

export type Setting = { id: string; key: string; value: string };

export type RuleKind = "must" | "must_not";
export type RuleScope = "project" | "path" | "node";
export type Rule = { id: string; text: string; kind: RuleKind; scope: RuleScope; target: string; by?: "human" | "agent" };

export type DecisionBy = "human" | "agent";
export type Decision = {
  supersedes?: string;
  id: string;
  text: string;
  pinned: boolean;
  path: string;
  nodeId: string;
  createdAt: string;
  by: DecisionBy;
};

export type NodePhase = "discover" | "define" | "build" | "verify" | "live";
export const NODE_PHASES: NodePhase[] = ["discover", "define", "build", "verify", "live"];

export type Criterion = { id: string; text: string; checked: boolean };
export type Step = { id: string; text: string; assignee: string; done: boolean };
/** Akce z portu karty: pipeline z knihovny, pořadí v poli je pořadí výrobní linky. */
export type NodeAction = { id: string; pipelineId: string; label: string; params: Record<string, string> };
/** Pravidlo uzlu z portu karty: co je pro tento uzel důležité a jak má fungovat. */
export type NodeRule = { id: string; text: string; kind: RuleKind };
/** Podklad z portu karty: nahraný obrázek (jméno souboru ve složce projektu), cesta ve zdroji projektu nebo URL. */
export type MaterialKind = "upload" | "source" | "link";
export type NodeMaterial = { id: string; kind: MaterialKind; path: string; caption: string };
/** Strom obsahu uzlu: očíslovaný blok textu se štítky, TODO, obrázky jako inspirací a stavem s větvením. */
export type BlockStatus = "open" | "met" | "unmet" | "blocked";
export const BLOCK_STATUSES: BlockStatus[] = ["open", "met", "unmet", "blocked"];
export type BranchKind = "block" | "node" | "action" | "none";
export type Branch = { kind: BranchKind; targetId: string; note: string };
export type Todo = { id: string; text: string; done: boolean; assignee: string };
export type ImageRef = { id: string; path: string; caption: string };
export type BlockState = { status: BlockStatus; condition: string; onMet: Branch; onUnmet: Branch; note?: string };
/** Tlačítko bloku, ze kterého se táhne vazba na jinou kartu. Nejvýš 8 na blok, popisek do 80 znaků. */
export type PortSpawn = { kind: "spawn"; template: { name: string; purpose?: string; spec?: Record<string, string>; text?: string; checks?: { id: string; command: string }[]; goal_mode?: "manual" | "until_checks_pass" } };
export type BlockPortDef = { id: string; label: string; status?: "chosen" | "rejected"; reason?: string; onMet?: PortSpawn };
export const MAX_BLOCK_PORTS = 8;
export const MAX_BLOCK_PORT_LABEL = 80;
export type Block = {
  id: string;
  /** Číslo v rámci uzlu: 1, 1.1, 1.2.3; přepočítává se při přesunu. */
  number: string;
  title: string;
  text: string;
  tags: string[];
  todos: Todo[];
  images: ImageRef[];
  state: BlockState;
  parentBlockId: string;
  /** Starší zápis porty nemá; čtěte přes blockPorts(). */
  ports?: BlockPortDef[];
};
export const emptyBranch = (): Branch => ({ kind: "none", targetId: "", note: "" });
/** Porty bloku s doplněným prázdným polem, aby starší uložený blok nerozbil kartu. */
export const blockPorts = (block: Pick<Block, "ports">): BlockPortDef[] => block.ports ?? [];

/** Uzavření karty. Agent smí `done` jen navrhnout (`by: "agent"`, `confirmed: false`); potvrzuje člověk. */
export type NodeDone = { confirmed: boolean; at: string; by: DecisionBy | "autonomy"; note: string };
export const emptyDone = (): NodeDone => ({ confirmed: false, at: "", by: "human", note: "" });

/** Zpráva agenta na vazbě: co udělal, když přecházel z jedné karty na druhou. Každé pole do 4000 znaků. */
export type EdgeReport = {
  log: string;
  summary: string;
  handoff: string;
  improvements: string;
  errors: string;
  updatedAt: string;
  by: DecisionBy;
  agent: string;
  /** Kdy se naposledy změnil neprázdný `handoff` (ISO čas); nastavuje aplikace, ručně nejde. Chybí = nepředáno. */
  sentAt?: string;
  /** Termín převzetí `YYYY-MM-DD` nebo `""`; volitelný, upravuje člověk. */
  due?: string;
};
export const MAX_REPORT_FIELD = 4000;
/** Pojmenovaná pole zprávy v pořadí, ve kterém je člověk i model čte. */
export type EdgeReportField = "log" | "summary" | "handoff" | "improvements" | "errors";
export const EDGE_REPORT_FIELDS: { id: EdgeReportField; label: string; hint: string }[] = [
  { id: "log", label: "Co se udělalo", hint: "Krok po kroku, co agent na této vazbě provedl." },
  { id: "summary", label: "Souhrn výsledku", hint: "Shrnutí pro dalšího agenta: co z toho platí." },
  { id: "handoff", label: "Předání", hint: "Kde pokračovat, co zůstalo rozdělané." },
  { id: "improvements", label: "Zlepšení", hint: "Na co narazil a čím by se to dalo zlepšit." },
  { id: "errors", label: "Chyby a varování", hint: "Co se pokazilo a na co si má dát pozor další agent." },
];

export type NodeWorkflowState = {
  downloadsUrl?: boolean;
  evidence?: import("@/editor/canvas/node-card/components/CardEvidence").CompletionEvidence;
  scenarioRun?: { command: string; at: string; passed: number; failed: number; logUrl: string; firstFailure: string };
  phase: NodePhase;
  criteria: Criterion[];
  steps: Step[];
  /** Starší uložený stav bloky nemá; čtěte přes nodeWorkflowOf(). */
  actions?: NodeAction[];
  rules?: NodeRule[];
  blocks?: Block[];
  materials?: NodeMaterial[];
  done?: NodeDone;
  /**
   * Která role agenta si tuhle práci pamatuje napříč projekty (`library/agent-roles.json`).
   * Volitelné a výchozí `null`: starší uložený stav roli nemá a karta bez role je platná —
   * paměť role se u ní jen nečte ani nezapisuje (docs/pamet-agentu.md).
   */
  agentRole?: string | null;
  /** Pipeline karty (port „pipeline“): etapy práce, testů, review, oprav a kritiků; řídí ji člověk. */
  stages?: import("@/editor/workflow/card-pipeline/logic/pipeline-model").CardPipeline;
  /** Podněty k dalšímu vývoji: ne-blokující nálezy review a kritiků; odškrtává člověk. */
  ideas?: import("@/editor/node-detail/ideas/logic/ideas-model").CardIdea[];
  /** Odkud karta vznikla ve schránce zadání: fragment a revize při vložení (zapisuje canvas-plan). */
  fragmentRefs?: import("@/editor/node-detail/brief-vault/logic/brief-vault-model").FragmentRef[];
  /** Zrušené kolo karty (rozhodnutí 23. 10.): server ho nepřijímá, čte ho jen model karty (kolo 1). */
  round?: import("@/editor/node-detail/rounds/logic/rounds-model").CardRound;
};
/** Stav uzlu se všemi bloky vyplněnými; oba bloky se ukládají vždy spolu. */
export type NodeWorkflowFull = Required<Omit<NodeWorkflowState, "evidence" | "scenarioRun" | "downloadsUrl" | "stages" | "ideas" | "fragmentRefs" | "round">> & Pick<NodeWorkflowState, "evidence" | "scenarioRun" | "downloadsUrl" | "stages" | "ideas" | "fragmentRefs" | "round">;

export type PipelineTemplate = { id: string; label: string; description: string };
export type PipelineCategory = { id: string; label: string; description: string; pipelines: PipelineTemplate[] };
export type PipelineLibrary = { categories: PipelineCategory[] };

export type TicketPriority = "low" | "normal" | "high";
export type TicketStatus = "open" | "doing" | "done";
export type Ticket = {
  id: string;
  title: string;
  priority: TicketPriority;
  status: TicketStatus;
  nodeId: string;
  sessionId: string;
  createdBy: DecisionBy;
};

export type DesktopState = {
  autonomy?: Record<string, { until: string; grantedAt: string; grantedBy?: string; note: string }>;
  settings: Setting[];
  rules: Rule[];
  decisions: Decision[];
  nodes: Record<string, NodeWorkflowState>;
  tickets: Ticket[];
  /** Zprávy agenta na vazbách grafu, klíč = id vazby. Starší uložený stav sekci nemá. */
  edges?: Record<string, EdgeReport>;
};

export const emptyDesktopState = (): DesktopState => ({
  settings: [],
  rules: [],
  decisions: [],
  nodes: {},
  tickets: [],
  edges: {},
});

export const emptyNodeWorkflow = (): NodeWorkflowFull => ({
  phase: "discover",
  criteria: [],
  steps: [],
  actions: [],
  rules: [],
  blocks: [],
  materials: [],
  done: emptyDone(),
  agentRole: null,
});

/** Uzel ze stavu s doplněnými bloky; chybějící uzel i starší zápis bez bloků dostanou prázdná pole. */
export const nodeWorkflowOf = (state: DesktopState, nodeId: string): NodeWorkflowFull => {
  const node = state.nodes[nodeId];
  return node
    ? {
        ...node,
        actions: node.actions ?? [],
        rules: node.rules ?? [],
        blocks: node.blocks ?? [],
        materials: node.materials ?? [],
        done: node.done ?? emptyDone(),
        agentRole: node.agentRole ?? null,
      }
    : emptyNodeWorkflow();
};

/** Všechny zprávy na vazbách; starší stav bez sekce `edges` se čte jako prázdná mapa. */
export const edgeReports = (state: DesktopState): Record<string, EdgeReport> => state.edges ?? {};

export type StateResponse = { revision: number; state: DesktopState; readOnly: boolean; graphChanged?: boolean };

/**
 * Balíček pro model (`GET /api/desktop-v3/node-brief`): jeden JSON, který model čte odshora dolů.
 * Tvar drží backend podle `docs/karta-pro-agenty.md`; frontend ho jen zobrazuje a kopíruje.
 */
export type NodeBrief = { schema: string } & Record<string, unknown>;



/** Levný souhrn paměti jedné karty: kolik z pěti polí je vyplněno, kdo psal naposled a kdy. */
export type AgentWorkspaceSummary = { filled: number; by: "human" | "agent"; updatedAt: string };

/**
 * Souhrn paměti všech karet (`GET /api/desktop-v3/agent-workspace-summaries`), klíč = ID uzlu.
 * Komentáře v položkách nejsou; na read-only mainu je `readOnly: true` a položky jsou prázdné.
 */
export type AgentWorkspaceSummaries = { readOnly: boolean; items: Record<string, AgentWorkspaceSummary> };

/** Jedna kontrola brány 1:1 z části 4 kontraktu `docs/synchronizace-pravdy.md`. */
export type SyncCheck = { id: string; name: string; passed: boolean; signal: string | null };

/** Verdikt Oracle nad jedním rozsahem: smí se commitnout a smí to do mainu. */
export type SyncVerdict = {
  scope: { kind: "area" | "sector" | "node"; id: string };
  state: "draft" | "waiting" | "green" | "closed";
  canCommit: boolean;
  canMerge: boolean;
  checks: SyncCheck[];
  blocking: string[];
  nextSteps: string[];
};

/** Nerovnost mezi zadáním, kódem a důkazy; `id` je stabilní, takže jde nález odložit. */
export type SyncSignal = {
  id: string;
  type: string;
  severity: "high" | "medium" | "low";
  subject: { scope: string | null; id: string | null; path: string | null; specRevision: number | null };
  evidence: { expected: string; actual: string; source: string };
  action: string;
};

/** Odpověď `GET /api/sync-report`: echo a verdikty pro celý projekt, jen ke čtení. */
export type SyncReport = {
  project: string;
  workspace: string;
  observedAt: string;
  gitHead: string | null;
  signals: SyncSignal[];
  verdicts: SyncVerdict[];
  counts: Record<string, number>;
};
