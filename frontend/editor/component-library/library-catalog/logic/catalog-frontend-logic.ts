// Kategorie Frontend – logika (blok 4 sektoru). Odvození dat a mutace stavu jsou čisté funkce
// v logic/<name>.ts s testem vedle; hook je jen vazba na React, kontext jen pro sdílený stav.
import type { CatalogItem } from "./library-catalog";

export const frontendLogicItems: CatalogItem[] = [
  {
    id: "fe-pure-model",
    category: "fe-logic",
    label: "Čistý model s testem vedle",
    hint: "logic/<name>.ts + <name>.test.ts: stav dovnitř, nový stav ven",
    icon: "ƒ",
    kind: "card",
    rules: {
      must: [
        "Funkce nevrací mutovaný vstup; vrací nový objekt.",
        "Test leží ve stejné složce jako modul a jmenuje se stejně.",
        "Model nezná React, DOM ani fetch.",
      ],
      mustNot: ["Žádné volání API z modelu.", "Žádná složka tests/ stranou od kódu."],
    },
    decomposition: [
      { title: "Typy", text: "Tvar stavu pojmenovaný jednou a sdílený dál." },
      { title: "Odvození", text: "Čtecí funkce: ze stavu spočítá, co dílek vykreslí." },
      { title: "Mutace", text: "Funkce stav → stav; rodič ji podá do mutate." },
    ],
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
    hint: "useState drží stav, hook jen podává akce modelu",
    icon: "⎔",
    kind: "card",
    rules: {
      must: [
        "Hook nemá vlastní logiku: volá funkce z modelu.",
        "Vrací dvojici stav + akce, nic jiného.",
        "Zápis do localStorage je v try/catch a nikdy nezhavaruje panel.",
      ],
      mustNot: ["Hook nesmí číst id projektu ani druh zdroje.", "Žádná business pravidla uvnitř komponenty."],
    },
    decomposition: [
      { title: "Model", text: "Čisté funkce se stavem (testované)." },
      { title: "Hook", text: "useState + useEffect pro uložení preference." },
      { title: "Rodič", text: "Zavolá hook jednou a rozdá stav dílkům v props." },
    ],
    template: [
      "// logic/use-panel.ts",
      "export function usePanel() {",
      "  const [state, setState] = useState(emptyPanel);",
      "  return { state, search: (q: string) => setState((s) => setQuery(s, q)) };",
      "}",
    ].join("\n"),
  },
  {
    id: "fe-form-state-split",
    category: "fe-logic",
    label: "Rozepsaná hodnota lokálně, hotová nahoru",
    hint: "Psaní nebliká přes celý strom, uloží se až hotová hodnota",
    icon: "✐",
    kind: "block",
    rules: {
      must: [
        "Rozepsaný text drží pole; nahoru jde na blur nebo Enter.",
        "Rodič dostane hotovou hodnotu jedním callbackem.",
        "Escape vrací pole na poslední uloženou hodnotu.",
      ],
      mustNot: ["Žádné ukládání na každý stisk klávesy.", "Žádná kopie hodnoty ve dvou stavech naráz."],
    },
    decomposition: [
      { title: "Lokální draft", text: "useState v poli; jen ono ví, co je rozepsané." },
      { title: "Commit", text: "onBlur a Enter pošlou hodnotu nahoru." },
      { title: "Reset", text: "Změna props zvenčí přepíše draft." },
    ],
    template: [
      "// components/CommitInput.tsx",
      "const [draft, setDraft] = useState(value);",
      "useEffect(() => setDraft(value), [value]);",
      "<input value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => onCommit(draft)} />",
    ].join("\n"),
  },
  {
    id: "fe-routing-as-data",
    category: "fe-logic",
    label: "Routing jako data",
    hint: "Cesty jsou pole záznamů, ne větvení v komponentě",
    icon: "⇉",
    kind: "block",
    rules: {
      must: [
        "Cesta je záznam s id, popiskem a podmínkou zobrazení.",
        "Výběr cesty je čistá funkce nad daty.",
        "Neznámá cesta má výchozí větev.",
      ],
      mustNot: ["Žádný řetěz if uvnitř komponenty.", "Žádná cesta odvozená z id projektu."],
    },
    decomposition: [
      { title: "Tabulka cest", text: "Data: id, popisek, kdo ji smí vidět." },
      { title: "Výběr", text: "routeFor(path) → záznam nebo výchozí." },
      { title: "Vykreslení", text: "Rodič podle záznamu složí obrazovku." },
    ],
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
    label: "Guard přihlášení bez tajemství v klientu",
    hint: "Klient jen skrývá, právo rozhoduje server",
    icon: "⚿",
    kind: "card",
    rules: {
      must: [
        "Guard je čistá funkce: stav relace → smí / nesmí.",
        "Server odpověď 401 vede na výzvu k přihlášení, ne na prázdnou obrazovku.",
        "Relace se drží v jednom kontextu.",
      ],
      mustNot: ["Žádný token, klíč ani heslo v kódu klienta.", "Žádné právo vyhodnocené jen v prohlížeči."],
    },
    decomposition: [
      { title: "Stav relace", text: "Kdo je přihlášený a co o něm víme." },
      { title: "canSee(state, need)", text: "Čistá funkce s testem vedle." },
      { title: "Odpověď serveru", text: "401 nebo 403 přepne obrazovku na přihlášení." },
    ],
    template: [
      "// logic/guard.ts",
      "export type Session = { signedIn: boolean; roles: string[] };",
      "export const canSee = (session: Session, need: string): boolean =>",
      "  session.signedIn && session.roles.includes(need);",
    ].join("\n"),
  },
];
