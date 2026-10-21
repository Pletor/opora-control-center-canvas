# Návrh jednostránkového OporaHubu

[Klikací HTML artefakt](oporahub-overview.html) vytvořil nainstalovaný Claude Code
pomocí instrukcí dovednosti `frontend-design` dne 2026-10-21 na výslovné přání
uživatele. Nejde o screenshot ani živý monitor projektu. Soubor nevolá síť,
neukládá stav a používá výslovně označená ukázková data.

Otevřete HTML přímo v prohlížeči nebo z kořene repozitáře spusťte:

```sh
python -m http.server 18761 --bind 127.0.0.1 --directory docs/design
```

Návrh má jeden přehled: přijatý plán, rozhodnutí člověka, práci agentů, důkazy
a další kroky. Kliknutí otevírá cílený detail; ✕ a Escape jej zavírají.
Obnova přepíná ukázkový, prázdný a chybový stav. Příklady `/api/v1/...` uvnitř
artefaktu jsou pouze ilustrativní tvar; skutečná aplikace používá existující
`/api/oporahub/...` podle [kontraktu rozhraní](../oporahub-overview.md) a
[execution API](../oporahub-executions.md).

Produkční komponenty používají skutečné modely a nesmějí přebírat ukázkové počty,
jména, časy, číselné revize ani domnělou vazbu kontrol ke kartě. Artefakt zůstává
samostatným návrhovým podkladem, nepřipojuje se jako iframe do aplikace.

Ověřeno headless Chromium: desktop1440×900 bez svislého či vodorovného přetečení,
mobil390px bez vodorovného přetečení, otevření API detailu a Escape, bez JS chyb.
Tato kontrola vzhledu neprokazuje živé API nebo přijetí plánu.
