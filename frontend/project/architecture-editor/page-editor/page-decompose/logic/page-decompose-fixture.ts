// Společná testovací mapa rozkladu stránky: doména „web“ s cestou Kampaň přes stránku Pěstování na Kontakt,
// komponenta Výzva v sekci cta, podstránka Rajčata (její komponenta k Pěstování nepatří) a nálezy kontroly mapy.
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import type { MapCheck } from "../../../domain-site/map-check/logic/map-check";

const node = (id: string, parentId: string | null, name: string, extra: Partial<CanvasNode> = {}): CanvasNode =>
  ({ id, parentId, kind: "node", name, purpose: "", x: 0, y: 0, ...extra });

export const GRAPH: Graph = {
  nodes: [
    node("web", null, "Web", { kind: "sector", site: { kind: "application", environments: [], journeys: [{
      id: "j1", name: "Kampaň", actor: "Začínající zahrádkář", pointA: "Rostliny mu hynou", pointB: "Má zelený balkon",
      steps: [
        { id: "s1", page: "nav", via: { do: "open" } },
        { id: "s2", page: "p1", label: "Zájem", shift: "Z „nejde mi to“ na „je to naučitelné“", objection: "Zase spam", via: { do: "click", text: "Pěstování" } },
        { id: "s3", page: "p2", label: "Poptávka", via: { do: "click", section: "cta", text: "Chci poradit" } },
      ] }] } }),
    node("p1", "web", "Pěstování", { site: { kind: "page", path: "/pestovani", goal: "Návštěvník si vyžádá radu", feel: "klidně",
      sections: [{ id: "hero", role: "hero", name: "Úvod", intent: "Pěstování bez stresu" },
        { id: "cta", role: "cta", name: "Výzva", intent: "Poradíme zdarma", moves: "Rozptýlí obavu ze spamu" }] } }),
    node("p2", "web", "Kontakt", { site: { kind: "page", path: "/kontakt" } }),
    node("c1", "p1", "Tlačítko výzvy", { card: { section: "cta", tech: "React", states: ["připraveno", "chyba"] } }),
    node("p3", "p1", "Rajčata", { site: { kind: "page", path: "/pestovani/rajcata", goal: "Recept" } }),
    node("c3", "p3", "Galerie rajčat"),
  ],
  edges: [
    { id: "e1", source: "c1", target: "p2", port: "next", carries: "navigation" },
    { id: "e2", source: "c3", target: "c1", port: "next" },
  ],
};

export const CHECK: MapCheck = { findings: [
  { rule: "journey.unrealized", journeyId: "j1", solverId: "p1", message: "Cesta Kampaň: z /pestovani na /kontakt nevede vazba (navigation, command, data ani sekce stránky)." },
  { rule: "journey.unrealized", journeyId: "j1", solverId: "p2", message: "Cesta Kampaň: z /kontakt na /pestovani nevede vazba (navigation, command, data ani sekce stránky)." },
  // Zpráva jmenuje /pestovani, ale přechod vychází z menu (místem řešení je aplikace): stránce nepatří.
  { rule: "journey.via-unknown", journeyId: "j1", solverId: "web", message: "Cesta Kampaň: krok Zájem čeká akci v sekci x, kterou menu nemá. stránka /pestovani nemá" },
  // Nález bez místa (kontrola čtená bez locate) se podle textu nepáruje.
  { rule: "journey.unrealized", journeyId: "j1", message: "Cesta Kampaň: z /pestovani na /kontakt nevede vazba." },
  { rule: "section.unrealized", nodeId: "p1", message: "Sekce hero nemá komponentu." },
  { rule: "state.no-error", nodeId: "c3", message: "Komponenta odesílá, ale nemá stav chyba." },
  { rule: "edge.carries-unset", edgeId: "e1", message: "Vazba neříká, co nese." },
] };
