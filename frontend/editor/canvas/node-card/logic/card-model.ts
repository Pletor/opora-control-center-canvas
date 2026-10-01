// Čistý model karty: z uzlu grafu a stavu Desktop v3 odvodí, co karta zobrazí. Bez Reactu,
// aby šel testovat samostatně a aby dílky karty (hlava, tělo, pata, porty) dostávaly hotová data.
import type { CanvasNode } from "@/shared/types/logic/types";
import type { BlockPortDef, BlockStatus, NodePhase, NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import { blockPorts } from "@/shared/desktop-state/logic/types";

export type CardPort = "next" | "action" | "rule" | "material";
export const CARD_PORTS: CardPort[] = ["next", "action", "rule", "material"];
export const PORT_LABEL: Record<CardPort, string> = { next: "další krok", action: "akce", rule: "pravidla", material: "podklady" };
/** Port „podklady“ otevírá blok, ale vazbu na jinou kartu z něj táhnout nelze. */
export const LINKABLE_PORTS: CardPort[] = ["next", "action", "rule"];

export const PHASE_LABEL: Record<NodePhase, string> = {
  discover: "objev",
  define: "definice",
  build: "build",
  verify: "ověření",
  live: "live",
};

/** Kolik štítků se vejde do paty karty; zbytek se sbalí do „+N“. */
export const VISIBLE_TAGS = 3;

/** Řádek bloku obsahu v kartě: jen kořenové bloky (bez rodiče) v pořadí čísel, s textem a tlačítky portů pod sebou. */
export type CardBlockRow = { id: string; number: string; title: string; status: BlockStatus; text: string; ports: BlockPortDef[] };

export function cardBlocks(workflow: Pick<NodeWorkflowFull, "blocks">): CardBlockRow[] {
  const key = (n: string) => n.split(".").map(Number);
  return workflow.blocks
    .filter((b) => !b.parentBlockId)
    .slice()
    .sort((a, b) => {
      const x = key(a.number), y = key(b.number);
      for (let i = 0; i < Math.max(x.length, y.length); i += 1) { const d = (x[i] ?? -1) - (y[i] ?? -1); if (d) return d; }
      return 0;
    })
    .map((b) => ({ id: b.id, number: b.number, title: b.title, status: b.state.status, text: b.text, ports: blockPorts(b) }));
}

export type CardView = {
  kind: "node" | "sector";
  name: string;
  purpose: string;
  phase: NodePhase;
  phaseLabel: string;
  tags: string[];
  hiddenTags: number;
  children: number;
  actions: number;
  rules: number;
  materials: number;
  openBlocks: number;
  blocks: number;
  rows: CardBlockRow[];
  /** Karta uzavřená člověkem: jen ke čtení, ztlumená, se zámkem v hlavě. */
  closed: boolean;
  /** Uzavření navržené agentem, které člověk zatím nepotvrdil. */
  doneProposed: boolean;
};

/** Štítky uzlu = sjednocení štítků všech bloků v pořadí prvního výskytu. */
export function nodeTags(workflow: Pick<NodeWorkflowFull, "blocks">): string[] {
  const seen: string[] = [];
  for (const block of workflow.blocks) for (const tag of block.tags) if (!seen.includes(tag)) seen.push(tag);
  return seen;
}

export function cardView(node: CanvasNode, workflow: NodeWorkflowFull, children: number): CardView {
  const tags = nodeTags(workflow);
  return {
    // Karta nezná komentář jako druh (ten kreslí CommentCard); Board sem komentář nikdy nepošle,
    // typ node.kind je ale širší, proto se tu neznámý druh chová jako "node".
    kind: node.kind === "sector" ? "sector" : "node",
    name: node.name,
    purpose: node.purpose,
    phase: workflow.phase,
    phaseLabel: PHASE_LABEL[workflow.phase],
    tags: tags.slice(0, VISIBLE_TAGS),
    hiddenTags: Math.max(0, tags.length - VISIBLE_TAGS),
    children,
    actions: workflow.actions.length,
    rules: workflow.rules.length,
    materials: workflow.materials.length,
    openBlocks: workflow.blocks.filter((b) => b.state.status === "open").length,
    blocks: workflow.blocks.length,
    rows: cardBlocks(workflow),
    closed: workflow.done.confirmed,
    doneProposed: workflow.done.by === "agent" && !workflow.done.confirmed,
  };
}

/** Počty do paty: jen nenulové, aby karta neukazovala „0 akcí“. Pořadí je pevné. */
export function footCounts(view: CardView): { value: number; label: string }[] {
  const plural = (n: number, one: string, few: string, many: string) => (n === 1 ? one : n >= 2 && n <= 4 ? few : many);
  const items = [
    { value: view.children, label: view.kind === "sector" ? plural(view.children, "uzel", "uzly", "uzlů") : plural(view.children, "poduzel", "poduzly", "poduzlů") },
    { value: view.openBlocks, label: plural(view.openBlocks, "otevřený blok", "otevřené bloky", "otevřených bloků") },
    { value: view.actions, label: plural(view.actions, "akce", "akce", "akcí") },
    { value: view.rules, label: plural(view.rules, "pravidlo", "pravidla", "pravidel") },
    { value: view.materials, label: plural(view.materials, "podklad", "podklady", "podkladů") },
  ];
  return items.filter((item) => item.value > 0);
}

/** Filtr štítků: karta je zvýrazněná, když některý její blok nese vybraný štítek; bez filtru všechny. */
export function matchesTagFilter(workflow: Pick<NodeWorkflowFull, "blocks">, filter: string): boolean {
  if (!filter) return true;
  return nodeTags(workflow).includes(filter);
}
