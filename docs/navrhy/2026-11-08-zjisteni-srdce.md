# Zjištění srdce: záložka u uzlu, podle zdrojů

Stav: kontrakt, 8. 11. 2026. Milník M1b navazuje na `2026-11-08-pletor-otazky-srdci.md` (M1). **Stavět až po živém
ověření M1:** přijetí, sloučení, restart 8740, aktivace promptu srdce a jedna celá otázka. Prompt srdce se mění po
jedné věci (lekce m11).

## Proč

Srdce zkoumá jedno téma a zjistí víc, než se vejde do odpovědi Pletorovi. Všechno, co zjistí, má ležet u uzlu,
kterého se téma týká, v jeho vlastní záložce a rozdělené podle zdroje. Když člověk variantu schválí, srdce pod tím
uzlem postaví oficiální plán úkolů a podrobnosti zůstanou v záložce. Ze stejných polí se později dá hledat napříč
projekty.

## Kam téma patří (rozhodnutí člověka 8. 11.)

Místo určuje struktura projektu, ne to, co má člověk zrovna otevřené:

1. Téma, které se týká stránky (`site.kind = page`), patří k uzlu té stránky, případně k její části v zanoření.
2. Téma, které ke stránce nepatří, je komponenta. Komponenta dostane vlastní uzel (sektor) s volným plátnem
   a ke stránkám se přiřadí později (`member` nebo `parent`).
3. Uzel vybírá srdce podle snímku a struktury. Když uzel neexistuje, založí ho přes `plan`. Uzel se zapíše
   k otázce (`pq_….node`) a Pletor ho člověku řekne, aby ho mohl opravit.

## Co se staví

| Část | Dnes | Změna |
|---|---|---|
| Uložení | Do schránky jdou jen ověřená fakta s URL, nejvýš 6 (`opora_research.vault_fields`). Fakta `soubor:řádek` se zahodí. Celý výsledek leží jen v `dilna/out/research/<id>.json`. | Všechna ověřená zjištění výzkumu se uloží jako seznam `findings` ve schránce u výzkumného fragmentu. Brána verdiktu (doklad = URL) se nemění. |
| Tvar zjištění | `evidence[{url,title,quote,accessedAt}]` | `findings[{source: {type: web\|youtube\|code\|vault, ref}, claim, quote, kind, layer, verified}]`. `ref` je kanonická URL, ID videa nebo `cesta@sha:řádek`. |
| Vazba na uzel | Uzel nese jen kořen schránky (`scope_node_id`). Srdce zapisuje do kořene „Výzkum srdce“ se `scope ""`. | `research --node N` najde nebo založí kořen schránky s `scope N` a ověří, že N v prostoru existuje. |
| Záložka | Šuplík karty: `spec, steps, lens, run, review, history`. Sektor: `spec, history`. | Nová záložka **Zjištění** u karty i sektoru, seskupená podle `source.type`. Znovu použije `ResearchSection` a `ResearchDetail` z `brief-vault-dock`. Vzhled je stejný pro všechny projekty. |
| Odpověď Pletorovi | `pletor-answer --ref` je volný text. | `--ref` odkazuje na výzkum nebo zjištění u uzlu. |
| Plán | Dávka `plan` má pole `parent: "@id"`. | Po `SCHVÁLENO` srdce postaví plán pod uzlem otázky. Před slibem ověřit, že validace grafu `parent` v libovolné hloubce pustí. |

Ověřit před stavbou (K8): kdo čte detail výzkumu, tedy `ResearchDetail.tsx`, `brief_vault_check`, node-brief
a lessons. Nové pole se nesmí rozbít starému čtenáři.

## Hledání napříč projekty (později)

Teď se nestaví žádný index. Zjištění ale nesou pole, která index potřebuje: projekt, uzel, kanonický zdroj,
tvrzení, citaci, `verified`, ID výzkumu a čas. Napojit je to možné na existující paměť (OpenViking) nebo
sémantické hledání (e5), až bude skutečná potřeba. Dnes ani jedno schránku nečte.

## Hotovo, když

- Výzkum s `--node` uloží všechna ověřená zjištění u toho uzlu. Zjištění z kódu a z YouTube se neztratí.
- Záložka Zjištění ukáže zjištění podle zdrojů u karty i sektoru v libovolném zanoření.
- Po `SCHVÁLENO` vznikne plán pod uzlem otázky.
- Cílené pytesty, `npm test` a `npm run build` jsou zelené, plus jedna živá otázka až po plán.
