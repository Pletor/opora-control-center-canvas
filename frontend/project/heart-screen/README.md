# Obrazovka srdce

Srdce (plátno 1, `heart-canvas/`) je samostatná obrazovka nejvyšší úrovně, ne záložka v liště Architektury projektu. Otevírá ji tlačítko „Otevřít canvas srdce“ v části „Pracovní workflow a pipeline srdce“ na stránce projektu (`project-setup/heart-pipeline/`); adresa `screen=heart`.

- `components/HeartScreen.tsx` – vlastní hlavička (← Projekt vrací na stránku projektu, jméno projektu, štítek plátna 1) a pod ní celé `HeartCanvas`. Nemá lištu architektury ani menu Editoru.
- Návrat (`onBack`) vyřizuje App (`setScreen("home")`).
