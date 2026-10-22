# Proces na kartě: každý údaj má své místo a ukazuje skutečný stav

Kontrakt (2026-10-15, ranní směna). Navazuje na `docs/pyramida.md` (úroveň 3 Karta) a `docs/karta-pro-agenty.md`
(pipeline, důkazy, kontroly). Důvod: vybraná karta do dneška skládala pod sebe fold za foldem (ke schválení,
Kontroly, deklarováno, Upravit důkazy, Potvrdit, Blokováno, Vychází z, pravidla, zdroj, realizace…). Když se
sešly, vznikl seznam, který se nedá zkontrolovat pohledem, a formulář důkazů nabízel člověku, aby vyplňoval
to, co hlásí agent. Měření na živých datech (project.sqlite, stav + snímky): 1 383 karet se stavem,
1 115 s důkazy, 5 576 záznamů `checksRun`, 1 057 profilů Kód, 109 Security, 98 Design; důkazy testů jsou
z 96 % „passed bez odkazu“ (lokální běh), review a merge z 81 % „passed s odkazem“. Proces a důkazy tedy
agenti používají naplno; člověk je jen čte.

## 1. Pět zón karty v pevném pořadí

| Zóna | Co ukazuje | Kdy je vidět |
|---|---|---|
| **Hlava** | druh, vrstva, model, kolo, zámek, odznaky (zadání se změnilo, podněty) | vždy |
| **Název a podstata** | | vždy |
| **Proces** | řada kuliček etap `●●●●` ┊ čtyři sloty dokladů `▢ Testy ▢ Security ▢ Review ▢ Merge` a pod nimi **jedna stavová věta** (+ tlačítko Potvrdit, když agent navrhl uzavření) | vždy; z dálky jen kuličky a sloty |
| **Kontrolní pás** | deset polí, co karta pro agenta má (cíl, hotovo, text, bloky, vazby, zdroj, kontroly, pipeline, důkazy, předávka) | plný detail |
| **Bloky s porty** | podmínky splnění, větvení, vazby | vždy |
| Pata | štítky, počty | plný detail |

Všechno ostatní (podrobnosti dokladů s odkazy a běhy kontrol, kdo kartu drží a soubory, co ji blokuje,
otázky na člověka, z čeho vychází, pravidla, zdroj, realizace commit / PR) je v **jednom foldu „Podrobnosti“**
na vybrané kartě (uzel i sektor), vždy ve stejném pořadí. Nic z toho se nezobrazuje jako samostatný řádek
nad bloky. Čipy dokladů v Podrobnostech berou barvu ze stejných slotů, aby neukázaly zelenou proti prázdnému slotu.

## 2. Sloty dokladů: pevná místa, skutečný stav

Čtyři sloty mají vždy stejné pořadí a místo, i když je karta bez pipeline. Slot je čtvereček (etapy jsou
kuličky, aby se nepletly). Stav slotu se **počítá** z toho, co je uložené, ne z toho, co agent napsal do
poznámky:

| Slot | Doloženo (plný) | Deklarováno bez dokladu (poloviční) | Selhalo (×) | Nevztahuje se (čárkovaný) | Nedoloženo (prázdný) |
|---|---|---|---|---|---|
| **Testy** | `evidence.tests = passed` **a** (odkaz, nebo ≥ 1 běh v `checksRun` s exit 0) **a** každá kontrola karty (`checks[]`, id + příkaz) má běh s exit 0 | etapa `test` prošla, ale důkaz chybí; `passed` bez odkazu a bez běhu; nebo doklad je, ale některá kontrola karty neběžela (tooltip řekne která) | `evidence.tests = failed`, nebo běh s exit ≠ 0, nebo etapa test uvízla | `not_applicable` (s důvodem v tooltipu) | jinak |
| **Security** | **poslední** kritik `hacker` v pipeline prošel (starší úspěch nedokládá novější audit; po selhání rozhoduje až opakování) | — | kritik `hacker` selhal a nemá naplánované opakování (čeká člověk) | — | pipeline kritika hacker nemá, ještě nebyl na řadě, nebo jeho opakování teprve čeká |
| **Review** | `evidence.review = passed` s odkazem | etapa `review` prošla bez důkazu, nebo `passed` bez odkazu | `evidence.review = failed` nebo etapa review uvízla | `not_applicable` | jinak |
| **Merge** | `evidence.merge = passed` s odkazem | `passed` bez odkazu | `failed` | `not_applicable` | jinak |

Běžící etapa (test, review, kritik hacker ve stavu `doing`) slot rozpulsuje stejně jako kuličku, a to i přes
starší selhaný důkaz (opakování po opravě má přednost před červenou). Uzavřená karta proces i sloty ponechá,
aby doklady šly přečíst pohledem i po uzavření.
Tooltip slotu Testy vypíše běhy kontrol jménem (`pytest ✓ · ruff ✓ · e2e ✗`) a co ještě neběželo, takže
druh testu (jednotkový, E2E, bezpečnostní…) je vidět z názvu kontroly; karta nepřidává další druh slotu.
Zelená v slotu znamená „doloženo“ ve smyslu `docs/karta-pro-agenty.md`: server odkazy nestahuje ani
neověřuje, jen hlídá, že doklad je uvedený a sedí s kontrolami.

## 3. Stavová věta: jedna, podle přednosti

Pod kuličkami je vždy právě jedna věta o tom, co se s kartou děje. Vzniká z frontier, přehledu práce,
pronájmu, pipeline a návrhu uzavření v tomhle pořadí (první platná vyhrává):

1. uzavřená → „Uzavřeno“ (zelená),
2. etapa uvízla (selhala bez opakování) → „Uvízlo: *název etapy* · čeká na tebe“ (jantar),
3. blok čeká na člověka → „Čeká na tebe: *otázka*“ (jantar),
4. agent navrhl uzavření → „Ke schválení“ + tlačítko **Potvrdit** (zamčené s důvodem, dokud sloty nejsou
   doložené) (jantar),
5. blokováno → „Blokuje: *karty*“ (červená),
6. hlášená práce (přehled práce) → „Pracuje *agent* · *doba*“ (modrá); jen držený pronájem bez hlášené činnosti
   → „Převzal *agent*“,
7. etapa na řadě → „Na řadě: *kdo: název*“ (tlumená),
8. bez pipeline → „Čeká na router“,
9. frontier hlásí k převzetí → „K převzetí“; jinak (frontier nenačtená, karta mimo ni) → „Čeká“.

Z dálky věta není; stav nese barva rámečku (frontier) a kuličky, z věty zůstane jen jantarová značka ◷
„potřebuje tebe“ (uvízlo, otázka, ke schválení). U návrhu uzavření věta nese i překážku („· blokuje: …“),
aby schvalování nezakrylo nesplněnou závislost.

## 4. Co mizí

- **Editor důkazů na kartě** (formulář tests / review / merge / kontroly): důkazy hlásí agent přes
  `agent-output.evidence`; člověk je čte. Mizí i akce `saveEvidence` a schopnost `can.saveEvidence`.
- Samostatné foldy „deklarováno“, „Kontroly“, „Blokováno“, „Vychází z“, převzetí, pravidla, zdroj, realizace
  nad bloky: obsah je v „Podrobnostech“, stav v slotech a větě.
- Čipy „👤 čeká“ a „+n ke schválení“ v řadě kuliček: nesou je věta a sloty.

## 5. Co se zatím nestaví (nálezy kritiků 2026-10-15, k rozhodnutí)

- Vazba dokladu na revizi zadání a kontrol: starý úspěšný běh po změně zadání nezastará (jen odznak „zadání se
  změnilo“ v hlavě). Vyžaduje zápis revize do `evidence` na serveru.
- Povinné sloty podle profilu (co smí být „nevztahuje se“): dnes jen pravidlo `[task]` / karta s kontrolami pro
  testy a merge (`evidence-readiness.ts`, server `completion_evidence.py`).
- Klik na slot nebo větu, který otevře a zaměří příslušný oddíl Podrobností; „Vrátit agentovi“ s důvodem u
  dokladu místo editoru.
- Stáří poslední aktivity u „Pracuje“ (bez odezvy) a rozlišení „bez pipeline“ od „ve frontě routeru“.

## 6. Kde to je v kódu

| Prvek | Kód |
|---|---|
| tvář karty (nahrazuje sloty dokladů, kuličky a stavovou větu na plátně) | `frontend/editor/canvas/card-face/` z `cards[]` agent-state, viz [oporahub-ui.md](oporahub-ui.md#editor-lean-tvář-karty-velín-a-živý-pás) |
| stavová věta (jen Kancelář) | `logic/card-state.ts` (+ test) |
| podrobnosti | `components/CardDetails.tsx` (skládá CardEvidence, CardChecks, WorkDetails, CardLease, CardFrontier, CardUpstream, pravidla, zdroj, realizaci) |
| data karty | `board/logic/layer-nodes.ts` (`face` = tvář karty z agent-state) |
| styl | blok „PROCES KARTY“ a „SLOTY DOKLADŮ“ v `styles/node-card.css` |
