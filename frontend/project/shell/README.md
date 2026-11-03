Kostra prostředí Projekt: `ProjectMapNavigation` v horní liště přepíná Architektura projektu / Studio (`ProjectMapKind` v `logic/project-view.ts`, adresa `projectView`; Studio viz `docs/studio.md`). Záměr stránky (`projectView=intent&page=<id>`) se otevírá z karty stránky, ne z lišty.

Srdce (plátno 1) do lišty nepatří: je to samostatná obrazovka `screen=heart` (`project/heart-screen/`) se vstupem ze stránky projektu. Staré odkazy `projectView=heart` a `projectView=graphify` vedou do architektury; pohled Graphify-out se stromem souborů je odstraněný (backend `/api/graphify` zůstává).
