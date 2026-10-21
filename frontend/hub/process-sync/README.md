# Proces Control Center

Čtecí projekce `GET /api/oporahub/process`, vložená do jednotného přehledu OporaHubu.
`logic/process-sync.ts` ověřuje scope a wire schema a vybírá existující detail.
`process-reader.ts` vlastní rušitelný život čtení; hook jen propojí stav s Reactem.
Sdílený `createPoller` plánuje obnovu 15 s po dokončení čtení, pouze při viditelném
dokumentu; návrat focusu požádá o čtení, pokud už jiné neběží. Požadavky se nepřekrývají.
Změna scope okamžitě skryje předchozí data a zneplatní odpovědi i chyby.

Komponenta zobrazuje stav, původ pozorování, další krok a kopírovatelné API.
Podnět vybere přesnou kartu v existujícím editoru zadání a zruší starou inspekci
návrhu; nikdy nepředá nodeId jako proposal ID. Žádný claim, přijetí, model ani poskytovatel se nespouští.
GitHub vazby jsou souhrnem prostoru, nikoli domyšlenou vazbou karta–PR.
