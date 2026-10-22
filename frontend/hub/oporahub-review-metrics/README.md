# oporahub-review-metrics

Zobrazuje malou infografiku metrik automatického review (drawer „Metriky review“ z paty OporaHubu): nálezy podle
závažnosti, přijetí a šum, kola na PR, čas do rozhodnutí člověka, pojistky (reverty, incidenty) a počet eval
případů s odkazem na `export.jsonl`. Data bere z `GET /api/oporahub/review-metrics` a `GET /api/oporahub/review-evals`
(docs/oporahub-review-identity.md); zrcadlo pro agenty je `script#oh-review-metrics`.
