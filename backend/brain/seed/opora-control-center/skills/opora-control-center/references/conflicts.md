# Konflikty návrhů: automatický rebase a jejich vyřešení

Kdy mě číst: agent-state ukazuje `waiting/auto_rebase_conflicts` nebo `stale_proposals`, nabízí
akci `proposal.resolve_conflict` nebo `rebase`, nebo ti zápis návrhu vrátil 409 kvůli staré hlavě.
Kontrakt: `docs/oporahub-auto-rebase.md`. Přijetí plánu zůstává **jen lidské**; nic z této
stránky neposouvá přijatou hlavu.

## Co dělá server sám

Po posunu přijaté hlavy server třícestně sloučí každý zastaralý návrh (zadání, graf, změny grafu,
obsah) po polích (`base` = co návrh viděl, `ours` = návrh, `theirs` = aktuální hlava):
čistý → nový návrh nad hlavou (autor `system`, `supersedes` = původní); redundantní → jen označí;
**stejné pole změněné oběma stranami → konflikt**; přeskočený → čeká na výslovný `rebase`.
Kroky `spec.steps` se porovnávají po `id` kroku.

## Akce `rebase` (přeskočený návrh)

`POST …/{id}/rebase` podle druhu návrhu (`/api/oporahub/changesets/{id}/rebase`,
`/api/oporahub/graph-proposals/{id}/rebase`, `/api/oporahub/content-changes/{id}/rebase`)
s `expectedAcceptedHead` (a u grafu `expectedGraphDigest`) z `preconditions` akce. Výsledek je nové
ID návrhu; 409 = předpoklady neplatí (karta zmizela, změněná architektura) → řeš jako konflikt.

## Akce `proposal.resolve_conflict`

1. `GET /api/oporahub/auto-rebase/conflicts/{id}`: položky `{key, base, ours, theirs}`.
2. Pro každý klíč rozhodni výslednou hodnotu: zachovej záměr obou stran, kde to jde (např. sjednoť
   acceptance, přečísluj kroky). Nejde-li to bez volby směru, nerozhoduj: napiš člověku obě varianty.
3. Vytvoř **běžný nový návrh** nad aktuální hlavou (stejný druh jako původní; [planner.md](planner.md))
   a zmiň v `subject` ID konfliktu.
4. Připoj ho: `POST /api/oporahub/auto-rebase/conflicts/{id}/resolve` `{resolutionProposalId}`
   (návrh musí být jiný a mít za rodiče aktuální hlavu).
5. Přijetí nového návrhu je na člověku (`accept`, `human_only`).

Hned spustit jeden průchod smyčky (např. po přijetí): `POST /api/oporahub/auto-rebase/run`.

## Historie a blame karty (jen čtení)

`GET /api/oporahub/history/card/{cardId}` a `GET /api/oporahub/blame/card/{cardId}`: kdo a kterou
revizí změnil které pole. U auto-rebase je `author` systémový, `originalAuthor` je původní autor.
Přepočet cache (`/api/oporahub/history/rebuild`) spouští jen člověk.
