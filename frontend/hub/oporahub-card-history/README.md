# oporahub-card-history

Zobrazuje odvozenou historii a blame jedné karty v detailu karty OporaHubu: přijaté revize, které se karty
dotkly (`GET /api/oporahub/history/card/{id}`), a pro každý aktuální klíč poslední revizi a autora
(`GET /api/oporahub/blame/card/{id}`). Auto-rebase ukazuje původního autora. Kontrakt: `docs/oporahub-auto-rebase.md`.
