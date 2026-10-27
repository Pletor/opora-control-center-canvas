# Návrhy nových karet a vazeb

OporaHub odděluje návrh struktury plánu od pracovního Canvasu. Agent nebo člověk
vytvoří neměnný návrh nových karet a vazeb; samotné vytvoření návrhu nic nepřidá
do plátna. Člověk před přijetím vidí konkrétní uzly, jejich zadání, vazby a umístění.
Přijatý graf a specifikace sdílejí jednu řadu revizí s dosavadními změnami zadání.

## První plán a další rozšíření

První návrh lze připravit i v prázdném zapisovatelném Canvasu bez přijaté revize.
Jeho přijetí vytvoří první revizi plánu. Pokud na plátně již obsah existuje,
první grafový návrh výslovně ukazuje také tento základ a zadání, která ještě
nebyla přijata. Zaškrtnutí přijetí základu se váže na přesný otisk zobrazeného
grafu. Není to dodatečné tvrzení, že staré revize už tento graf schválily.

Další návrh rozšiřuje předchozí přijatý graf pouze o prohlédnuté přírůstky.
Nesouvisející rozpracované změny grafu se tím nestávají přijatými. Návrh také
nesmí skrytě přijmout změněné zadání existující přijaté karty; takovou změnu
nejprve vyřešte v panelu změn zadání.

Nové karty dostanou stabilní ID a normalizované zadání již při vytvoření návrhu.
Přijetí znovu negeneruje ID ani umístění. Agent-office může převzít novou kartu
až po přijetí a splnění kontrol execution protokolu.

Pokud revize obsahuje přijatý graf, vykonávání navíc ověřuje jeho významovou
shodu s pracovním grafem. Neschválené uzly, vazby nebo změněné odpovědnosti
vykonávání zablokují. Pouhá prezentace se posuzuje stejně jako v kontextu zadání;
přesun do jiné oblasti už může změnit význam. Kontrola je zatím konzervativní
pro celý graf, nikoli jen pro okolí jedné karty. Starší revize bez přijatého
grafu nadále používají výslovně omezenou kontrolu přijatých specifikací.

## Současné souběžné návrhy

Návrh zaznamenává přijatého rodiče, pozorovaný graf a význam odkazovaných
existujících uzlů. Pokud jiný návrh mezitím postoupí přijatou revizi nebo změní
graf, je potřeba výslovný přenos na nového rodiče (`rebase`).

Přenos vytváří nový neměnný návrh a zachovává ID jeho nových uzlů. Dva nezávislé
přírůstky lze spojit, pokud zůstávají jejich opěrné uzly a odkazy platné.
Změněný nebo odstraněný odkazovaný uzel, obsazené ID a konfliktní zdrojový odkaz
se odmítnou. Nové umístění se případně vypočítá v přeneseném návrhu před review.
Existující karty se nepřesouvají bez samostatné změny.

## Rozsah API

Prefix je `/api/oporahub/graph-proposals`. Scope vždy určuje `project` a `workspace`.
Seznam vrací nejvýše 100 souhrnů; plný graf a zadání se načítají až v detailu.

| Cesta | Obsah |
|---|---|
| `GET /context` | Přijatá hlava, otisk pracovního grafu a potřeba prvního přijetí základu |
| `GET /` | Souhrny návrhů a přijatá hlava |
| `GET /{id}` | Neměnný návrh včetně zobrazeného základu a přírůstků |
| `POST /` | Scope, `parentRevision`, `expectedGraphDigest`, `subject`, `plan` |
| `POST /{id}/rebase` | Scope, `expectedAcceptedHead`, `expectedGraphDigest` |
| `POST /{id}/accept` | Totéž a `adoptBaseGraphDigest`; vyžaduje člověka |

`plan` obsahuje seznamy `nodes` a `edges`. Uzel má lokální `ref`, druh `node`,
`sector` nebo `area`, název a volitelného rodiče a specifikaci
`spec: {goal, non_goals, acceptance}`. Vazba má `from`, `to` a volitelný
`port: "next"` a volitelný druh toku `carries` (`navigation | data | command | event`, jen u `next`,
nikdy se nedoplňuje). Odkazy jsou lokální názvy návrhu nebo `@ID` existujícího uzlu.
Podporované volitelné údaje uzlu zahrnují účel, rozměry, polohu a zdrojový odkaz.
Server odmítá neznámá pole; klient nepředává vypočtená ID ani odvozený výsledek.

Starší neprázdný graf bez přijatého manifestu lze výslovně převzít návrhem
s prázdnými `nodes` a `edges`. Po vzniku manifestu se prázdný přírůstek odmítá;
prázdné plátno potřebuje skutečný první prvek. Kontrola a potvrzení přebíraného
základu i zadání zůstávají povinné.

Jeden přírůstkový návrh je omezen na 200 nových uzlů a 600 vazeb. Pro úpravy
a odstranění existujících uzlů slouží [druhá verze návrhu grafu](oporahub-graph-changes.md).
Přímé změny sdílené architektury, bran, kontrol a procesního stavu tento
přírůstkový protokol neposkytuje.

## Uložení, migrace a obnova

Graf, specifikace, manifest přijatého grafu a posun přijaté hlavy se zapisují
v jedné SQLite transakci. Opakované přijetí stejného návrhu vrátí jeho původní
přijatou revizi; neposune hlavu zpět, pokud již existují další revize.

Lokální projekty používají dosavadní databázový graf. Gitový pracovní prostor
se při prvním přijetí grafového návrhu přepne na databázové úložiště grafu.
Původní soubor zůstává zachovaný jako záloha, nikoli živá kopie. Další běžné
úpravy i obnova pracovního snímku používají nové úložiště. Poškozený záznam
vyvolá chybu; server se nesmí tiše vrátit ke starému souboru.

Před nasazením zálohujte celá data včetně databáze. Samotná složka workspace
po přepnutí není úplnou zálohou grafu. Archivace ponechává databázová data
archivovaného prostoru. Návrat databázové zálohy staré migrace architektury
se po uložení návrhu grafu, přijetí plánu (i lokálního), přepnutí grafu nebo
zařazení do řízeného vykonávání odmítá i s `force`, aby
neodstranil novější graf a historii ani neobnovil zaniklé oprávnění agenta.
Povolená obnova starší zálohy doplní aktuální kompatibilní schéma databáze;
nejde proto o bajtově shodnou obnovu databáze.
Starý server bez podpory této autority nelze bezpečně spustit nad stejnými daty.

Obnova pracovního snímku není vrácení přijaté historie. Nevrací GitHub kód,
nasazení ani přijaté výsledky běhů. Stejně jako ostatní změny OporaHubu tato
vrstva předpokládá jeden serverový proces Canvasu.
