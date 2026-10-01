// Kategorie Frontend – logika. Odvození dat a mutace stavu jsou čisté funkce v logic/<name>.ts,
// hook je jen vazba na React. Tvar prvku: library-catalog.ts, kontrakt docs/menu-a-katalog.md §B2.
import type { CatalogItem } from "./library-catalog";

export const frontendLogicItems: CatalogItem[] = [
  {
    id: "fe-pure-model",
    category: "fe-logic",
    label: "Čistý model s testem vedle",
    purpose: "Stav a jeho změny jako čisté funkce v logic/<name>.ts: stav dovnitř, nový stav ven.",
    relates: [
      "@test-unit-beside",
      "@fe-hook-over-model",
      "Rodič předá mutaci do mutate; dílky dostanou odvozená data v props.",
    ],
    done: [
      "Modul neimportuje React, DOM ani fetch.",
      "Vedle leží <name>.test.ts a npm test prochází.",
    ],
    invariants: [{ kind: "must_not", text: "Mutace nemění vstupní stav, vrací nový objekt." }],
    template: [
      "// logic/panel-model.ts",
      "export type PanelState = { open: boolean; query: string };",
      "export const emptyPanel = (): PanelState => ({ open: false, query: \"\" });",
      "export const setQuery = (state: PanelState, query: string): PanelState => ({ ...state, query });",
    ].join("\n"),
  },
  {
    id: "fe-hook-over-model",
    category: "fe-logic",
    label: "Hook nad čistým modelem",
    purpose: "Hook drží stav přes useState a podává akce z modelu; vlastní logiku nemá.",
    relates: [
      "@fe-pure-model",
      "Volá ho rodič jednou a rozdá výsledek dílkům.",
      "Preference aplikace se ukládá pod jediný klíč, nikdy per projekt.",
    ],
    done: [
      "Hook vrací stav a akce, každá akce je jedno volání funkce z modelu.",
      "Bez localStorage (soukromé okno) panel funguje s výchozím stavem.",
    ],
    invariants: [{ kind: "must_not", text: "Hook nečte id projektu ani druh zdroje (sourceKind)." }],
    template: [
      "// logic/use-panel.ts",
      "export function usePanel() {",
      "  const [state, setState] = useState(emptyPanel);",
      "  return { state, search: (q: string) => setState((s) => setQuery(s, q)) };",
      "}",
    ].join("\n"),
  },
  {
    id: "fe-routing-as-data",
    category: "fe-logic",
    label: "Routing jako data",
    purpose: "Cesty jsou pole záznamů a výběr cesty je čistá funkce, ne větvení v komponentě.",
    relates: ["@fe-pure-model", "@fe-auth-guard", "Rodič podle vybraného záznamu složí obrazovku."],
    done: [
      "Neznámá cesta vrací výchozí záznam.",
      "routeFor má test vedle.",
    ],
    invariants: [],
    template: [
      "// logic/routes.ts",
      "export const ROUTES = [",
      "  { id: \"projekt\", label: \"Projekt\" },",
      "  { id: \"editor\", label: \"Editor\" },",
      "] as const;",
      "export const routeFor = (id: string) => ROUTES.find((r) => r.id === id) ?? ROUTES[0];",
    ].join("\n"),
  },
  {
    id: "fe-auth-guard",
    category: "fe-logic",
    label: "Přihlášená sekce a guard",
    purpose: "Stav relace v jednom kontextu a guard, který podle něj ukáže obsah nebo výzvu k přihlášení.",
    relates: [
      "@sec-server-validation",
      "@sec-no-secrets",
      "@fe-routing-as-data",
      "Odpověď serveru 401/403 přepne obrazovku na přihlášení.",
    ],
    done: [
      "canSee(session, need) je čistá funkce s testem vedle.",
      "Nepřihlášený vidí výzvu k přihlášení, ne prázdnou stránku.",
    ],
    invariants: [
      { kind: "must_not", text: "Guard v klientu jen skrývá obsah; o právu rozhoduje server." },
      { kind: "must_not", text: "V klientském kódu není token, klíč ani heslo." },
    ],
    steps: [
      { title: "SessionContext", text: "Jediný zdroj pravdy o relaci pro celou sekci." },
      { title: "MemberGuard", text: "Dostane stav relace v props, vrací obsah nebo výzvu." },
      { title: "session-api.ts", text: "Přihlášení a odhlášení voláním serveru." },
    ],
    template: [
      "// logic/guard.ts",
      "export type Session = { signedIn: boolean; roles: string[] };",
      "export const canSee = (session: Session, need: string): boolean =>",
      "  session.signedIn && session.roles.includes(need);",
    ].join("\n"),
  },
];
