# card-face

Tvář karty na plátně Editoru: druh, kdo kartu drží, název, jeden stavový řádek (zdraví · etapa · důvod),
postup kroků a nejvýš jedna patička (brána / blokace / rozhodnutí). Data bere výhradně z `cards[]` a
`decisions[]` agent-state (`logic/card-face.ts`, test `card-face.test.ts`); pod 45 % zoomu kreslí glyf.
Klik na rozhodnutí otevře detail karty přes `frontend/hub/oporahub-card-drawer/open.ts`.
