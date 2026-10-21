# Omezení oprávnění běhů

Samostatný dílek zobrazuje aktuální policy, rodinu přijatého zadání, spotřebu pokusů/oprav a omezené historie policies, allocations a cancellations z `/api/oporahub/execution-budgets`.

Hook vlastní App. Zápis používá neměnný potvrzovaný snapshot, accepted/policy CAS a stabilní requestId. Změna karty, scope, přijatého plánu nebo policy zneplatní potvrzení. Nejistá mutace se automaticky neopakuje. Read-only konfigurace a lidské oprávnění zrušit starý běh jsou odlišné.

Zrušení konkrétní execution je v sesterském dílku execution-receipts. Jde o odebrání oprávnění; nezaručuje ukončení celého stromu procesů ani finanční/tokenový limit. Kontrakt: `docs/oporahub-execution-budgets.md`.
