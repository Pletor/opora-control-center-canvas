export type TimelineGroup = "Zadání" | "Práce" | "Ověření" | "Předávky" | "Kód";
export type TimelineItem = { at: string; group: TimelineGroup; label: string; detail?: string };

/** Chronologie DNA: prázdné či neplatné časy jdou až nakonec a nemění pořadí známých událostí. */
export function timelineItems(items: TimelineItem[]): TimelineItem[] {
  return items.slice().sort((left, right) => {
    const a = Date.parse(left.at);
    const b = Date.parse(right.at);
    if (Number.isNaN(a)) return Number.isNaN(b) ? 0 : 1;
    if (Number.isNaN(b)) return -1;
    return a - b;
  });
}

export function timelineForGroup(items: TimelineItem[], group: TimelineGroup | "Vše"): TimelineItem[] {
  return group === "Vše" ? items : items.filter((item) => item.group === group);
}

export type CardDnaInput = {
  title: string; goal?: string; nonGoals?: string; acceptance?: string;
  pipeline: { name: string; note?: string }[]; evidence: string[];
  realization?: { commit?: string; path?: string };
};

/** Přenosný Markdown: minimum, z něhož LLM obnoví cíl, cestu práce i doloženou realizaci. */
export function buildCardDna(input: CardDnaInput): string {
  const lines = [
    `# DNA karty: ${input.title}`,
    "", "## Zadání", input.goal ?? "—",
    "", "## Mimo rozsah", input.nonGoals ?? "—",
    "", "## Přijetí", input.acceptance ?? "—",
    "", "## Pipeline", ...input.pipeline.map((stage) => `- ${stage.name}${stage.note ? ` — ${stage.note}` : ""}`),
    "", "## Důkazy", ...input.evidence.map((item) => `- ${item}`),
    "", "## Realizace", `- commit: ${input.realization?.commit ?? "—"}`, `- cesta: ${input.realization?.path ?? "—"}`,
  ];
  return lines.join("\n");
}
