// Přehled Schránky po disciplínách (docs/schranka-neurony.md §6): pokrytí každé disciplíny (listy zadání
// a kolik z nich už pracuje jako karty) a průměrná predikční chyba bran `verified` (0 = předpověď sedí,
// 1 = úplně vedle). Počítá se nad celým stromem rozsahu, ne nad vybranou disciplínou. Bez Reactu.
import { coverageOf, type Coverage, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { DISCIPLINES, UNASSIGNED, filterByDiscipline, viewOf, type DisciplineView } from "./disciplines";

export type DisciplineStat = {
  id: DisciplineView;
  coverage: Coverage;
  /** Listy, které už mají kartu (vloženo, MVP vloženo, změněno po vložení). */
  asCards: number;
  /** Průměr `predictionError` ověřených fragmentů disciplíny, `null` = zatím nic ověřeno. */
  meanError: number | null;
  verified: number;
};

/** Řádky přehledu v pořadí tabulky §2 (jen disciplíny s obsahem), nezařazené na konci. */
export function disciplineStats(roots: VaultNode[]): DisciplineStat[] {
  const errors = new Map<DisciplineView, number[]>();
  const stack = [...roots];
  while (stack.length) {
    const node = stack.pop()!;
    stack.push(...node.children);
    const value = node.kind === "brief" ? node.gates?.predictionError : null;
    if (typeof value === "number") errors.set(viewOf(node), [...(errors.get(viewOf(node)) ?? []), value]);
  }
  return [...DISCIPLINES.map((item) => item.id), UNASSIGNED].flatMap((id) => {
    const coverage = coverageOf(filterByDiscipline(roots, id));
    const values = errors.get(id) ?? [];
    if (!coverage.leaves && !values.length) return [];
    const mean = values.length ? Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) / 100 : null;
    return [{ id, coverage, asCards: coverage.inserted + coverage.mvpInserted + coverage.changed, meanError: mean, verified: values.length }];
  });
}
