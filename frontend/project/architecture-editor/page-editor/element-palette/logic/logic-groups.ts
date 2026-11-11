// Paleta logiky plátna 2 podle otázky člověka (docs/navrhy/2026-11-10-platno-2.md): Kdo, Kdo smí, Co musí splnit,
// Co se děje, S čím, Napojení. Popisky jsou vlastní plátnu 2; Editor (plátno 3) má dál své `ELEMENT_GROUPS`. Bez Reactu, test vedle.
import type { ElementKind } from "@/shared/types/logic/types";
import { ELEMENT_LABELS } from "@/editor/canvas/create-dialog/logic/element-palette";
import type { PageIconName } from "../../components/PageIcon";

export type LogicKind = { kind: ElementKind; label: string };
export type LogicGroup = { question: string; icon: PageIconName; kinds: LogicKind[] };

export const LOGIC_GROUPS: LogicGroup[] = [
  { question: "Kdo", icon: "user", kinds: [{ kind: "actor", label: "Uživatel" }] },
  { question: "Kdo smí", icon: "security", kinds: [{ kind: "permission", label: "Přístup" }] },
  { question: "Co musí splnit", icon: "rule", kinds: [{ kind: "condition", label: "Podmínka" }, { kind: "constraint", label: "Omezení" }] },
  { question: "Co se děje", icon: "backend", kinds: [{ kind: "action", label: "Akce" }, { kind: "process", label: "Proces" }, { kind: "form", label: "Formulář" }] },
  { question: "S čím", icon: "database", kinds: [{ kind: "entity", label: "Data" }, { kind: "storage", label: "Úložiště" }] },
  { question: "Napojení", icon: "logic", kinds: [{ kind: "service", label: "Služba" }, { kind: "input", label: "Vstup" }, { kind: "output", label: "Výstup" },
    { kind: "event", label: "Událost" }, { kind: "api_contract", label: "API kontrakt" }] },
];

/** Popisek a symbol druhu na štítku prvku; druh mimo paletu (starší data) dostane popisek Editoru a symbol napojení. */
export function logicLook(kind: ElementKind): { label: string; icon: PageIconName } {
  for (const group of LOGIC_GROUPS) {
    const found = group.kinds.find((item) => item.kind === kind);
    if (found) return { label: found.label, icon: group.icon };
  }
  return { label: ELEMENT_LABELS[kind], icon: "logic" };
}
