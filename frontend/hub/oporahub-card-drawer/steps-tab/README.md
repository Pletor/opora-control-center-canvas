# Záložka Kroky

Kroky plánu z přijatého zadání (`fields.steps`, docs/oporahub-plan-steps.md) se stavem z `cards[].steps.items` agent-state (souhrn všech běhů karty, hotový krok zůstává hotový; bez něj z `stepResults` nejnovějšího běhu) a důkazy z nejnovějšího běhu: postup, náhled DAG po hloubce závislostí, akceptace kroku a aktuální krok (`cards[].steps.current`). Bez kroků poctivě „nenapojeno“. Logika: `logic/step-status.ts` (test vedle).
