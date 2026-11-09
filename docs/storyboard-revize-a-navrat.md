# Revize a přijetí Storyboardu

Pracovní historie je v projektové SQLite tabulce `storyboard_revisions`.
`StoryboardService` a `/api/storyboard` zůstávají rozhraním editoru. Uložení není
přijetí. Přijetí používá současné content proposals/manifests a accepted head,
typ `storyboard`, pole `storyboard`. Editor nabídne **Navrhnout přijetí** a otevře
existující review OporaHubu. Kontroly role, přesného návrhu, revizí a review policy
zůstávají v původním rozhraní. Nevzniká další schvalovací stav.

Historický zdroj lze číst přes
`GET /api/storyboard?project=…&workspace=…&nodeId=…&revision=…`.

## Nasazení a převzetí

Nejprve ukončit starší procesy zapisující do stejných dat, zazálohovat projektová
data a nasadit kompatibilní čtenáře i zapisovatele. Nový content kind musí umět
každý čtenář přijatých manifestů; starý binární kód jej odmítne. Souběžný provoz
starých a nových zapisovatelů nad stejnými daty není podporován.

První čtení existujícího JSON jej importuje pod projektovým a SQL zámkem.
Opakování je idempotentní. Revize, tombstone, čas i existující ID se zachovají.
Chybějící ID momentů se doplní jednou stejně jako ve starším editoru. Původní
soubor zůstává beze změny. Prázdné čtení nevytváří SQL řádek. Po první SQL revizi
se JSON nikdy nepoužije k přepsání novější historie. Nic se automaticky nepřijímá.

Uložení, smazání a změna skici připojují revize. Přijetí zapisuje zdroj, manifest
a accepted head v jediné SQL transakci; chyba vrátí všechny změny. Obnovení
historické scény vytvoří novou revizi. Historii nelze aktualizovat ani mazat.

## Předávky

Nové předávky obou execution protokolů vyžadují přijatý Storyboard a připínají
accepted revizi, content manifest, zdrojovou revizi, digest i snapshot relevantních
scén. Jejich další změna vyvolá řízený konflikt; nesouvisející sourozenec nikoliv.
Historické `captured-at-claim` assignmenty zůstávají přesně nezměněné a nezískávají
zpětně přijetí. V2 SQL zdroje ani verze se nemění; Storyboard má vlastní ověřený pin.

## Výslovný návrat pracovních dat

Zastavit všechny zapisovatele. Novým kompatibilním kódem otevřít `CanvasService`
nad vlastním datovým kořenem a zavolat
`backend.editor.storyboard.storyboard_export.export_workspace(canvas, project,
workspace, Path(novy_adresar))`. Cíl musí být nový adresář. Export odmítá přepis,
obsahuje poslední pracovní JSON a `export.manifest.json` s identitami/revizemi. SQL ani
původní soubory nemění. Po kontrole exportu z něj obnovit pracovní soubory starého
editoru; ponechané původní JSON už mohou být zastaralé.

Nové přijaté manifesty a assignmenty se nikdy nepřepisují ani nemažou. Starý kód
bez nového content kind nesmí tyto kontrakty obsluhovat; export pracovních dat
nenahrazuje kompatibilní rollback kódu. Při návratu k SQL zachovat novější historii,
nepoužívat soubory jako druhou autoritu a nepřepisovat je do existujících SQL revizí.
Případné další úpravy provedené starším editorem převzít výslovným uložením přes
nové `/api/storyboard` s aktuální SQL revizí; vzniknou nové revize, nikoliv přepis.
