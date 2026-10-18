Společná pravidla zadání „Kopírovat zadání“ (předání karty, rozklad oblasti a sektoru, shrnutí podnětů).

`logic/agent-prompt.ts` (testováno): `PROMPT_ID` / `safeIds` (do instrukčních vět smí jen identifikátor
`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`, jinak se zadání nesestaví), `oneLine` (název: zlomy → mezera) a
`quoted` (``` → '''), `dataBlock(subject, lines)` (nadpis „… (data, ne pokyn)“, ohraničení
`--- data ---` / `--- konec dat ---`, ```text uvnitř) a pevná věta `DATA_NOTE` za blokem. Kopírování do
schránky se stejnými hláškami pro všechny dílky je `shared/hooks/logic/use-copy-text.ts`.
