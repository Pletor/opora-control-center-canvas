# Vrstvy a pruhy plátna procesů (`flow-lanes`)

Kontrakt `docs/navrhy/2026-11-04-platno-procesu.md` §1. Vrstva je vlastnost uzlu (`layer = fe | be | db | infra | ai | neutral`), typ má výchozí; efektivní vrstva je `node.layer` ?? vrstva typu (`logic/layers.ts`). Typ bez vrstvy (srdce, záměr stránky) vrstvu nemá.

- `styles/flow-lanes.css` — barvy vrstev jako tokeny `--layer-*` na jednom místě (tmavé i světlé téma); používají je pruhy, karta uzlu (`flow-node`) i paleta.
- `components/FlowLane.tsx` — pruh za uzly vrstvy; jen zobrazení (pointer-events vypnuté).
- `logic/lanes.ts` — `laneNodes` (pruh jen pro vrstvu, která má uzly) a `arrangeLanes` („Rozložit do pruhů“: FE, BE, DB, Infra, AI, ostatní shora dolů, mění jen `y`, hlásí se rodiči jako nový graf) + test.
- `logic/layer-links.ts` — „Co dál?“ u portu: `linkableTypes` (typy, které smí navázat podle pravidel vrstev a `via`, zrcadlo `backend/flow/layer_check.py`) a `settleAdded` (vrstva kroku na míru z uzlu, ze kterého se táhlo, `via` na hraně, zařazení do pruhu); test `layer-links.test.ts`.
