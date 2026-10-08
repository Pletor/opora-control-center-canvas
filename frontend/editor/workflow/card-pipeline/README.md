Pipeline karty (pátá kulička „pipeline“): proces karty z etap práce, testů, review, oprav a tří kritiků (hodný uživatel, vyčuraný, hacker).

- Proces je autonomní: určuje ho router (`POST /api/desktop-v3/pipeline`), každou etapu dělá vlastní relace agenta. Šablony profilů drží jen server (`backend/editor/agent_memory/card_pipeline.py`).
- `logic/pipeline-model.ts` — typy, popisky, souhrn (na řadě, opakování, čeká na člověka) a ubírající zásahy člověka (odebrat, přeskládat, přeskočit, přepsat).
- `components/PipelineBlock.tsx` — čipy profilů (jeden klik = přestavět přes `BlockApi.routePipeline`), kdo a proč proces určil, pruh stavu, etapy. `PipelineStageRow.tsx` — jedna etapa.
- Kontrakt pro agenty: `docs/karta-pro-agenty.md` → Pipeline karty. Neplést s akcemi (`pipelineId` z knihovny).
