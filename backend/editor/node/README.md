Obsah jednoho uzlu: text, zadání, deník, odkazy, kresby a jejich wireframe projekce, odstraňování s obnovou. Každý modul vlastní svou tabulku revizí.

`removals.py` dělá náhled a smazání uzlu, vazby, výběru (`kind: "selection"`, čárkami spojená id) a odpojení projektu. `removal_recovery.py` před smazáním uloží jednorázový záznam obnovy (`removal_restores`: graf, `state.nodes`/`state.edges`, vynulované větve, prostor agenta) a `POST /api/remove/restore` ho jednou použije. Kontrakt: `docs/hromadne-mazani.md`.
