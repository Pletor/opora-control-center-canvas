# Záložka Review & PR

PR karty, hlava a čerstvost vůči cílové větvi, všechny důvody brány merge (`GET /api/oporahub/review-jobs/gates`), nálezy review stejného PR (`GET /api/oporahub/review-jobs`), ověření lidé proti požadovanému počtu a formální důkazy (`hub/oporahub-proofs`). Logika: `logic/review-view.ts` (test vedle).
