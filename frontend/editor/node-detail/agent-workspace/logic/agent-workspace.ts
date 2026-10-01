// Čistý model pracovního prostoru agenta (`docs/karta-pro-agenty.md`, sekce „Pracovní prostor
// agenta“): pět pojmenovaných sekcí, které si model vede u jedné karty (uzel, sektor i oblast) mezi
// jednotlivými revizemi. Tenhle modul nic nenačítá ani neukládá — to dělá use-agent-workspace.ts —
// jen tvaruje data a pravidla kolem nich: limit délky sekce, které sekce se mezi dvěma verzemi
// liší (pro částečný zápis) a odkaz na jednu sekci karty.

/** Klíč jedné sekce prostoru, ve stejném pořadí, v jakém je člověk i model čte. */
export type SectionKey = "frame" | "log" | "failures" | "fixes" | "handoff";

export type AgentWorkspaceSections = Record<SectionKey, string>;

export type AgentWorkspaceBy = "human" | "agent";

/** Tvar `workspace` z GET/POST `/api/desktop-v3/agent-workspace`; revize a readOnly nese odpověď zvlášť. */
export type AgentWorkspaceRecord = AgentWorkspaceSections & {
  updatedAt: string;
  by: AgentWorkspaceBy;
};

export type SectionDef = { key: SectionKey; label: string; hint: string };

/** Popisky a nápovědy pro pět polí inspektoru, v pořadí rámec → postup → chyby → opravy → předávka. */
export const SECTIONS: SectionDef[] = [
  { key: "frame", label: "Rámec a směr", hint: "Co je cílem této práce a kudy k němu vede cesta." },
  { key: "log", label: "Postup", hint: "Pracovní postup, krok po kroku." },
  { key: "failures", label: "Co se nepovedlo", hint: "Co se nepovedlo a proč, aby to další agent neopakoval." },
  { key: "fixes", label: "Úspěšné opravy", hint: "Co se pokazilo a čím se to spravilo." },
  {
    key: "handoff",
    label: "Předávka",
    hint: "Konkrétní kroky: kam se podívat, který soused nebo potomek nese souvislost, kudy podle vazeb pokračovat.",
  },
];

/** Limit délky jedné sekce; stejná hodnota jako backend (`agent_workspace.py`). */
export const MAX_SECTION = 12000;

/** Prázdný prostor: stejný tvar jako revize 0 na serveru (viz karta-pro-agenty.md). */
export function emptyWorkspace(): AgentWorkspaceRecord {
  return { frame: "", log: "", failures: "", fixes: "", handoff: "", updatedAt: "", by: "human" };
}

/** Odkaz na jednu sekci karty; model ho používá ve zprávě na vazbě i ve vlastním prostoru místo kopírování textu. */
export function sectionLink(nodeId: string, key: SectionKey): string {
  return `opora://agent-workspace/${nodeId}#${key}`;
}

/** Ořízne text sekce na MAX_SECTION znaků, aby psaní nikdy neposlalo delší text, než server přijme. */
export function clampSection(text: string): string {
  return text.length > MAX_SECTION ? text.slice(0, MAX_SECTION) : text;
}
