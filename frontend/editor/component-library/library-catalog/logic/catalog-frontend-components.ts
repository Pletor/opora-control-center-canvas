// Kategorie Frontend – komponenty (blok 2 sektoru). Každá položka nese stejný příběh: rodič skládá
// dílky, data tečou dolů v props, události bublají nahoru callbackem a ukládá jen rodič.
import type { CatalogItem } from "./library-catalog";

export const frontendComponentItems: CatalogItem[] = [
  {
    id: "fe-form-validated",
    category: "fe-components",
    label: "Formulář s validací",
    hint: "Rozepsané hodnoty drží pole, hotovou hodnotu dostane rodič",
    icon: "✎",
    kind: "card",
    rules: {
      must: [
        "Rozepsaná hodnota zůstává v poli, nahoru jde až hotová (onCommit).",
        "Validace je čistá funkce v logic/ s testem vedle.",
        "Chybová hláška patří k poli a je česky.",
      ],
      mustNot: [
        "Dílek nevolá fetch ani mutate; ukládá rodič.",
        "Žádná validace jen v klientu: server ji dělá znovu.",
      ],
    },
    decomposition: [
      { title: "FormField (dílek)", text: "Jedno pole: popisek, hodnota v props, onChange a onCommit nahoru." },
      { title: "form-model.ts (logika)", text: "validate(values) → chyby; čistá funkce, test vedle." },
      { title: "Rodič formuláře", text: "Drží hodnoty, sbírá chyby, volá uložení; jediné místo se zápisem." },
    ],
    template: [
      "// logic/form-model.ts",
      "export type FormErrors = Record<string, string>;",
      "export function validate(values: { email: string }): FormErrors {",
      "  const errors: FormErrors = {};",
      "  if (!values.email.includes(\"@\")) errors.email = \"Zadejte e-mail ve tvaru jmeno@domena.\";",
      "  return errors;",
      "}",
    ].join("\n"),
  },
  {
    id: "fe-member-area",
    category: "fe-components",
    label: "Členská sekce: stav + guard + API",
    hint: "Přihlášený obsah: stav relace, stráž cesty a volání API na jednom místě",
    icon: "◍",
    kind: "card",
    rules: {
      must: [
        "Stav relace žije v jednom kontextu, ne v každém dílku zvlášť.",
        "Guard rozhoduje jen o zobrazení; právo ověřuje server.",
        "Nepřihlášený vidí důvod a cestu dál, ne prázdnou stránku.",
      ],
      mustNot: [
        "Žádné tajemství, token ani heslo v klientském kódu.",
        "Dílek uvnitř sekce nečte relaci sám; dostane ji v props.",
      ],
    },
    decomposition: [
      { title: "SessionContext (stav)", text: "Kdo je přihlášený; jediný zdroj pravdy pro celou sekci." },
      { title: "MemberGuard (dílek)", text: "Dostane stav v props, vrací obsah nebo výzvu k přihlášení." },
      { title: "session-api.ts (logika)", text: "Přihlášení a odhlášení voláním serveru; žádné tajemství v klientu." },
    ],
    template: [
      "// components/MemberGuard.tsx",
      "export default function MemberGuard({ signedIn, children, onSignIn }: {",
      "  signedIn: boolean; children: ReactNode; onSignIn: () => void;",
      "}) {",
      "  if (signedIn) return <>{children}</>;",
      "  return <button type=\"button\" onClick={onSignIn}>Přihlásit se</button>;",
      "}",
    ].join("\n"),
  },
  {
    id: "fe-list-select",
    category: "fe-components",
    label: "Seznam s výběrem",
    hint: "Řádky dostane dílek hotové, vybraný řádek hlásí nahoru",
    icon: "☰",
    kind: "card",
    rules: {
      must: [
        "Vybrané id drží rodič, dílek dostane selectedId v props.",
        "Řádky jdou dovnitř už odvozené (logic/list-model.ts).",
        "Výběr jde myší i klávesnicí (šipky, Enter).",
      ],
      mustNot: ["Dílek si seznam nefiltruje ani netřídí sám.", "Žádný stav výběru duplikovaný ve dvou místech."],
    },
    decomposition: [
      { title: "ListRow (dílek)", text: "Jeden řádek: popisek, stav vybráno, onSelect nahoru." },
      { title: "list-model.ts (logika)", text: "rows(data, query) → hotové řádky k vykreslení; test vedle." },
      { title: "Rodič seznamu", text: "Drží vybrané id a dotaz, skládá řádky, hlásí změnu dál." },
    ],
    template: [
      "// logic/list-model.ts",
      "export type Row = { id: string; label: string };",
      "export const rows = (items: Row[], query: string): Row[] =>",
      "  items.filter((item) => item.label.toLowerCase().includes(query.trim().toLowerCase()));",
    ].join("\n"),
  },
  {
    id: "fe-tabs-one-active",
    category: "fe-components",
    label: "Záložky s jednou aktivní",
    hint: "Přepínač pohledu: aktivní záložka je stav rodiče, ne dílku",
    icon: "⊞",
    kind: "card",
    rules: {
      must: [
        "Aktivní záložka je jedna hodnota v rodiči (union typ, ne string).",
        "Záložka má role=\"tab\" a aria-selected.",
        "Varianta se řeší třídou blok__tab--active, ne inline stylem.",
      ],
      mustNot: ["Dílek si aktivní záložku nepamatuje sám.", "Žádné skryté záložky bez popisku pro čtečku."],
    },
    decomposition: [
      { title: "Tabs (dílek)", text: "Vykreslí seznam záložek z dat a hlásí onTab nahoru." },
      { title: "Panel (dílek)", text: "Obsah jedné záložky; nezná ostatní." },
      { title: "Rodič", text: "Drží aktivní záložku a rozhoduje, který panel se skládá." },
    ],
    template: [
      "// components/Tabs.tsx",
      "export default function Tabs({ tabs, value, onTab }: {",
      "  tabs: { id: string; label: string }[]; value: string; onTab: (id: string) => void;",
      "}) {",
      "  return (",
      "    <nav role=\"tablist\">",
      "      {tabs.map((tab) => (",
      "        <button key={tab.id} role=\"tab\" aria-selected={tab.id === value} onClick={() => onTab(tab.id)}>",
      "          {tab.label}",
      "        </button>",
      "      ))}",
      "    </nav>",
      "  );",
      "}",
    ].join("\n"),
  },
  {
    id: "fe-parent-composes",
    category: "fe-components",
    label: "Rodič skládá dílky",
    hint: "Kostra feature složky: components/ logic/ styles/ README.md",
    icon: "▦",
    kind: "card",
    rules: {
      must: [
        "Každý viditelný celek je složka feature s README.md.",
        "Soubor delší než zhruba 200 řádků se dělí na další dílek.",
        "Dílek dostává hotová data v props a změnu hlásí callbackem.",
      ],
      mustNot: ["Dílek nezná plátno, API ani sourozence.", "Žádný zápis mimo rodiče."],
    },
    decomposition: [
      { title: "components/Feature.tsx", text: "Rodič: importuje dílky, drží stav, ukládá." },
      { title: "components/FeaturePart.tsx", text: "Dílek: props dolů, callback nahoru, nic víc." },
      { title: "logic/feature-model.ts", text: "Odvození dat a mutace stavu jako čisté funkce + test." },
      { title: "styles/feature.css", text: "Jeden soubor na složku, BEM s předponou bloku." },
    ],
    template: [
      "// components/Feature.tsx",
      "export default function Feature({ items, onPick }: { items: Item[]; onPick: (id: string) => void }) {",
      "  return (",
      "    <section className=\"feature\">",
      "      {items.map((item) => <FeaturePart key={item.id} item={item} onPick={onPick} />)}",
      "    </section>",
      "  );",
      "}",
    ].join("\n"),
  },
];
