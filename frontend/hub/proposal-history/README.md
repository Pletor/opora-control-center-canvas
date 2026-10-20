# proposal-history

Návrhy uloženého zadání, historie a historický diff v OporaHubu.
`App` drží `useOporaProposals`; `ProposalHistory` dostává data a callbacky bez vlastních zápisů.
Výběr rozsahu pochází přímo z grafu Canvasu a nezávisí na reportu Oracle.

Hook zachytí `head` a `contextVersion`, pošle je beze změny s návrhem a při odmítnutí
neopakuje zápis. Obnova kontextu je výslovná. Generace požadavků brání přepsání
nového rozsahu starou odpovědí. `proposals.test.ts` ověřuje tuto ochranu a zachování
pozorovaných očekávání. Historie ukazuje posledních 100 záznamů, diff porovnává
vybraný záznam s rodičem; starý záznam bez snímku vrátí vysvětlení serveru.

Nejde o schvalovací UI. Návrh zachycuje již uložené zadání, není izolovaným patchem.
Přijetí do plánu pochází ze staršího `inMain`, nikoli z důkazu nové nezávislé kontroly.
Kontrakt: `docs/oporahub.md`. CSS používá blok `proposal-history`.
