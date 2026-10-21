# Proces Control Center

Čtecí projekce `GET /api/oporahub/process`, vložená do jednotného přehledu OporaHubu.
`logic/process-sync.ts` ověřuje scope a wire schema a vybírá existující detail.
`process-reader.ts` vlastní rušitelný život čtení; hook jen propojí stav s Reactem.
Sdílený `createPoller` plánuje obnovu 15 s po dokončení čtení, pouze při viditelném
dokumentu; návrat focusu požádá o čtení, pokud už jiné neběží. Požadavky se nepřekrývají.
Změna scope okamžitě skryje předchozí data a zneplatní odpovědi i chyby. Obnova
stejného scope ponechá poslední pozorování označené jako neaktuální a pozastaví
akce. Tlačítka zůstávají v DOM i pro návrat focusu z detailu; aria-disabled a guard
zakazují jejich aktivaci. Chyba zachová pouze výslovně historický pohled.

Komponenta zobrazuje stav, původ pozorování, další krok a kopírovatelné API.
Podnět vybere přesnou kartu v existujícím editoru zadání a zruší starou inspekci
návrhu; nikdy nepředá nodeId jako proposal ID. Chybějící vybraná karta se nenahrazuje
první kartou a obnova přesnou volbu zachová. Žádný claim, přijetí, model ani poskytovatel se nespouští.
GitHub vazby jsou souhrnem prostoru, nikoli domyšlenou vazbou karta–PR.
