/** Části velínu AGI Pletor v pořadí z kontraktu (§3); od V4 jsou všechny funkční. */
export const PARTS = [
  { id: "prehled", label: "Přehled", ready: true },
  { id: "mozek", label: "Mozek a LLM", ready: true },
  { id: "hlas", label: "Hlas", ready: true },
  { id: "srdce", label: "Srdce", ready: true },
  { id: "podklady", label: "Podklady", ready: true },
  { id: "dilna", label: "Dílna", ready: true },
  { id: "monitoring", label: "Monitoring", ready: true },
  { id: "rozhovor", label: "Rozhovor", ready: true },
  { id: "nastaveni", label: "Nastavení", ready: true },
] as const;

export type PartId = (typeof PARTS)[number]["id"];
export const DEFAULT_PART: PartId = "prehled";

/** Část z `?part=`; chybějící nebo neznámá hodnota je Přehled. */
export function parsePart(search: string): PartId {
  const value = new URLSearchParams(search).get("part");
  return PARTS.find((part) => part.id === value)?.id ?? DEFAULT_PART;
}

/** Je adresa stránkou velínu (`?screen=pletor`)? */
export const isDashboardRoute = (search: string) => new URLSearchParams(search).get("screen") === "pletor";

/** Adresa velínu s danou částí; ostatní parametry (projekt, prostor) zůstanou. */
export function withPart(search: string, part: PartId): string {
  const q = new URLSearchParams(search);
  q.set("screen", "pletor");
  q.set("part", part);
  return "/?" + q;
}
