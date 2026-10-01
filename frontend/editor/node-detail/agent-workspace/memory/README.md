# agent-workspace/memory

Segment **Paměť role** na ploše Text → Agenti. Pět polí vedle je paměť jedné karty; tenhle celek je
o patro výš: drží zkušenost *kompetence*, která kartu přežije. Kontrakt a mapování na OpenViking
popisuje `docs/pamet-agentu.md`, backend je `backend/api/editor/memory_routes.py` a
`backend/memory/memory_service.py`.

Tři pravidla, která tenhle dílek nikdy neporuší:

1. **Nic se nestane samo.** Panel při připojení přečte jen přepínač aplikace (`GET /api/memory/status`)
   a knihovnu rolí (`GET /api/memory/roles`). Vybavení, zápis, půjčka i rozdání klíčů rolím běží až
   na stisk tlačítka; žádný polling, žádný automatický zápis do sdílené paměti role.
2. **Prázdný výsledek se nevydává za „role si nic nepamatuje“.** Stav (`disabled`, `unavailable`,
   `skipped`, `configured`) i větu důvodu vypisuje panel tak, jak přišly ze serveru.
3. **Půjčka není vlastní zkušenost.** Položky s původem `lent:<role>` mají vlastní skupinu, vlastní
   štítek i barvu a nikdy se nemíchají mezi `self` a `project`.

- `logic/agent-memory.ts` — čistý model: stav panelu a skupiny (`memoryModel`, `groupByOrigin`,
  „Vlastní zkušenost“ / „Tento projekt“ / „Zapůjčeno od <role>“), skóre jako pojmenovaná podobnost
  (`formatScore`), volby role (`roleOptions`), kdy se smí číst, psát a půjčovat (`canRecall`,
  `canRemember`, `canLend`) a těla požadavků s přesnými klíči kontraktu (`recallPayload`,
  `rememberPayload`, `lendPayload`). Stav `needs_provisioning` nese `missingRoleIds`/
  `missingRoleLabels` (role bez klíče u OpenVikingu) a rozdání klíčů `provisionPayload` +
  `provisionSummary` (věta „Založeno / Beze změny / Nepodařilo se“ se jmény rolí). Navíc
  `briefRoleMemory` (paměť, kterou už nese balíček karty) a `memoryQuery` (napsaný dotaz → cíl
  karty → identita karty). Test leží vedle.
- `logic/agent-role.ts` — role karty jako čtení a mutace stavu Desktop v3 (`agentRoleOf`,
  `setAgentRole`). Nová cesta ukládání tu nevzniká: je to obyčejná mutace uzlu, kterou pošle
  rodič do `useDesktopState().mutate`, takže role jede stejnou revizí a zámkem jako fáze nebo bloky.
- `logic/use-agent-memory.ts` — síťový stav: stav a role jednou při připojení, `recallNow`,
  `remember`, `lend` a `provision` jen na pokyn. Každá odpověď má pořadové číslo a scope, takže
  pozdní výsledek po přepnutí karty nic nepřepíše; zápis drží zámek, aby dvojí klik nezaložil dva
  zdroje. `provision` volá `POST /api/memory/provision` a hned poté `refresh()`, takže stav po
  založení klíčů je vždy nová odpověď serveru, ne přání kliknutí.
- `components/AgentMemoryPanel.tsx` — rodič segmentu: pruh stavu (vypnuto → „Zapni ji v Nastavení →
  Napojení“, nedostupné → důvod a adresa, `needs_provisioning` → banner „Role zatím nemají klíče…“
  se seznamem chybějících rolí a tlačítkem „Založit klíče rolí“), výběr role karty, dotaz s
  tlačítkem „Vybavit“, skupiny výsledků a pod nimi akce. Paměť z briefu (`context.roleMemory`) je
  výchozí seznam s poznámkou „zatím z briefu karty“. Roli panel neukládá — hlásí ji callbackem
  `onRoleChange` nahoru.
- `components/AgentMemoryItem.tsx` — jedna položka: štítek původu, podobnost, adresa a text.
- `components/AgentMemoryActions.tsx` — „Zapamatovat“ (druh note/lesson/decision, text do 12 000
  znaků, samostatné tlačítko; u zamčené karty se formulář vůbec nekreslí) a „Zapůjčit od role…“.
- `styles/agent-memory.css` — BEM blok `agent-memory`: `__banner`, `__banner--unavailable`,
  `__banner--needs-provisioning`, `__role`, `__recall`, `__group`, `__item`,
  `__origin--self|--project|--lent`, `__score`, `__form`.

Co tenhle dílek nedělá: nespouští žádný model (extrakci si dělá OpenViking sám), nezapisuje do
paměti na pozadí (to je věc backendu při uložení a uzavření karty), nekreslí se v inspektoru
(`layout="stack"` segment vůbec nemontuje) a neukládá nic per projekt — přepínač paměti je
nastavení celé aplikace v Nastavení → Connectors.
