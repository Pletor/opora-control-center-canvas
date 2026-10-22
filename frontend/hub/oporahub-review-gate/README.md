# oporahub-review-gate

Zobrazuje krok Review v detailu karty: stav brány merge, pravidlo, které ji drží, otevřené důležité
nálezy, bezpečnostní review, počet ověřených lidí proti požadovaným schválením, vlastní kontroly agenta,
zastarání proti cílové větvi a neúplnou šablonu PR. Data bere z `GET /api/oporahub/review-jobs/gates`
(docs/oporahub-review-jobs.md) a akce z dokumentu agent-state.
