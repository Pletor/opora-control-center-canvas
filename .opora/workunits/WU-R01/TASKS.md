# R01 / T-01

- RED→GREEN: uložit a znovu načíst zadání přes API.
- RED→GREEN: stale CAS, historie, validace a scope/main guard.
- RED→GREEN: UI save/reload, error retention a přepínání uzlů.
- Izolovat E2E od portu a dat produkce; review, test a lokální checkpoint.

Oracle: tests/test_node_specs.py, e2e/node-spec.spec.ts. Nezávislý reviewer ověří význam tvrzení. Další nálezy pouze NEXT NODE.
