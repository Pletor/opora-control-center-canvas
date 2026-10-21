# plan-changes

Samostatný návrh změny `goal`, `non_goals`, `acceptance` existujících karet.
`App` vlastní `usePlanChanges`; komponenta zobrazuje data a předává akce callbacky.
Editor nemá přímé volání ukládání zadání. Zápis do Canvasu nastane až při přijetí.

Výchozí základ lze přijmout jen jednou a UI ukáže všechny jeho dokumenty. Návrh
nese zachycenou přijatou revizi, digest grafu a skutečnou pracovní revizi karty.
Prohlídka před přijetím ukazuje přijaté, uložené pracovní i navržené hodnoty, aby
nezůstaly skryté starší nepřijaté změny. Přijetí není nezávislé review ani důkaz kódu.
Rebase je výslovné vytvoření nového návrhu; původní se nemění.

Po zápisu nebo konfliktu se očekávání invalidují; klient nikdy neopakuje mutaci.
Obnova a přepnutí karty zahazují rozepsané úpravy, jak říkají popisky. Při změně
projektu/prostoru a obnově se ruší platnost starých síťových odpovědí i lokálního draftu.
Sedm testů v `logic/plan-changes.test.ts` ověřují izolaci, preconditions a viditelnost
pracovního driftu v porovnání. Kontrakt: `docs/oporahub.md`.

Úspěšné přijetí invaliduje aktuální rozsah i po odchodu z panelu. App předává úzký `specRefreshRevision` přes NodePanel do NodeSpecEditor; ostatní lokální editory se neremountují a rozepsané zadání zůstává chráněné konfliktní revizí.
