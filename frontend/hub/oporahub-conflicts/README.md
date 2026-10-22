# oporahub-conflicts

Zobrazuje konflikty automatického rebase (`GET /api/oporahub/auto-rebase/conflicts`): pro každé pole
návrhu stranu `base` (přijato u rodiče), `ours` (návrh) a `theirs` (aktuální hlava). Člověk zvolí stranu,
zkopíruje návrh řešení, založí běžný nový návrh nad hlavou a jeho ID připojí ke konfliktu
(`POST …/conflicts/{id}/resolve`). Kontrakt: `docs/oporahub-auto-rebase.md`.
