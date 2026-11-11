# card-face

Tvář karty na plátně Editoru (plátno 3, návrh `docs/new-ui/Neonový dashboard OPORA_ Projekt a Editor.png`): štítek
s kódem a druhem („E-144 Výzkum“), kdo kartu drží, velký název s kruhem postupu, stavová pilulka (Hotovo / V realizaci /
Čeká / Přijatý / V přípravě / Na kontrole / Čeká na tebe / Problém) s počitadlem „2/4 kroky“, tečky Z/K/S/B a nejvýš
jedna patička (brána / blokace / rozhodnutí). Stav bere výhradně z `cards[]` a `decisions[]` agent-state
(`logic/card-face.ts`, test `card-face.test.ts`); pod 45 % zoomu kreslí glyf (kruh postupu + název).

Druh a kód (`logic/face-family.ts`, test vedle; počítá `board/logic/layer-nodes.ts` do `NodeCardData.kind`):
druh je předpona v názvu (`effectiveType`, týž jako backend `cards[].kind`): `[research]` Výzkum, `[prototype]` Návrh,
`[task]` Úkol (vše pracovní krok, fialově), `[gate]` Ověření (šeřík), `[grilling]` Rozhodnutí (oranžový kosočtverec);
bez předpony doménová role `element.kind`: `api_contract` Kontrakt (zeleně), `condition` Rozhodnutí; jinak neutrální
„Krok“ (sektor „Sektor“). Kód je písmeno rodiny (E krok, C kontrakt, V ověření, R rozhodnutí) a pořadí podle záměru
`cards[].order`, bez pořadí prvních 4 znaků id. Pilulka a počitadlo jsou jen jiné znění tváře (`facePill`, `faceCounter`).

Rám karty nese druh (`node-card--family-*`, tokeny `--card-*`), styl čáry nese růst (`logic/face-growth.ts`: semínko a
návrh čárkovaně, vývoj a doloženo plně; kruh postupu v barvě růstu). Vybraná nebo běžící karta (`node-card--live`)
svítí modře. Přednost rámu: chybějící zdroj > problém > čeká na tebe (zlatá) > vybraná / běží > druh. Tečky Z/K/S/B:
K z `cards[].mirror` (ok zelená, part modrá, bad plná červená, `null` čárkovaně), B z `cards[].future` (clean zelená,
warning modrá, blocked červená, `null` čárkovaně). Legenda barev je samostatný dílek `editor/canvas/card-legend`.
Klik na rozhodnutí otevře detail karty přes `frontend/hub/oporahub-card-drawer/open.ts`.
Pod stavovým řádkem stojí odznak PR v barvách GitHubu (`face.pr` z `cards[].pr`, dílek `frontend/shared/pr-badge`); uzavřená karta ho nemá.

Pohyb jen ze skutečného stavu: karta ve stavu `decision` („čeká na tebe“, `logic/card-face.ts`) má čárkovaný zlatý prstenec `::after` s animací `node-card-await` (1,85 s); tečka živého dělníka pulzuje (1,1 s). Při `prefers-reduced-motion` bez animace, prstenec svítí napevno.

Stopa karty (docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md, B). Poslední změnu a osy návrh / realizace / ověření tvář neukazuje, žije v živé kartě; `logic/face-change.ts` drží jen odznak pořadí a popisek „kdy“ pro boční panel stopy:

- **Pořadí:** číslo `cards[].order` je v kódu karty (`E-302`); `face.order` (`3·02`) zůstává v `data-oh-order`.
- **Stopa práce:** počitadlo kroků je tlačítko (`data-oh-open-trail`, bez kroků „stopa ›“). Klik ohlásí `onTrail` → akce karty `trail` → App otevře boční menu se stopou práce karty (`editor/block-panel`, režim karty bez bloku).
