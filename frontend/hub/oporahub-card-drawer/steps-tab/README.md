# Záložka Kroky

Kroky plánu z přijatého zadání (`fields.steps`, docs/oporahub-plan-steps.md) se stavem z `stepResults` výsledků nejnovějšího běhu: postup, náhled DAG po hloubce závislostí, akceptace kroku a aktuální krok (`cards[].steps.current`). Bez kroků poctivě „nenapojeno“. Logika: `logic/step-status.ts` (test vedle).
