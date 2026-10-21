# OporaHub v procesu Control Center

OporaHub je společný přehled procesu, nikoli druhý zapisovatelný stavový automat.
Canvas vlastní přijatý plán a pipeline karty, execution ledger oprávnění a nahlášené
výsledky, GitHub pozorování kódu. Projekce tyto podklady spojí pro aktuální projekt
a workspace; čtení nevolá model, GitHub ani poskytovatele vykonavatele.

## Kontrakt integrace

- `GET /api/oporahub/process?project=…&workspace=…` vrací
  `schema: opora.process-sync/1`, scope, aktuální přijatou revizi, čas načtení,
  položky karet a výslovné meze výřezu. Volitelný `nodeId` vrátí jedinou kartu.
- Položka obsahuje identitu karty, pipeline, shodu pracovního zadání s přijatým,
  dostupnost převzetí podle uložených podkladů, souhrn posledního execution a jeho vztah k revizi,
  počty nahlášených výsledků a konkrétní další krok s odkazy na nativní API.
  Evidovaný běh není nové potvrzení autority; tu znovu ověří claim, heartbeat
  nebo odevzdání. Vyčerpaný počet nových pokusů sám neukončuje stávající běh.
- Nahlášený výsledek žádá nezávislou kontrolu. PR merge, lidské dokončení karty,
  ověření a nasazení jsou samostatné skutečnosti. Historický výsledek se při
  změně přijaté revize nepřepíše ani nevydává za výsledek aktuální revize.
- Procesové soubory `/api/processes` nemají workspace ani vazbu na přijatou
  revizi. Mohou být odkázané jako projektová historie, nesmějí měnit execution
  ani se automaticky synchronizovat do `done`.
- Běžný `node-brief` doplní odkaz na tuto projekci a execution/proposal API.
  Jde o živou orientaci; nenahrazuje neměnné assignment ani neposkytuje token.
- Zlepšení z práce a kontroly se vracejí jako nativní návrhy zadání, grafu nebo
  obsahu s aktuálním základem. Jejich přijetí nadále podléhá lidskému review a CAS.
  Agent nemění vlastní zadání automatickým potvrzením.

## Rozhraní

Přehled OporaHubu obsahuje modul „Proces Control Center“ s kartami, stavem,
dalším krokem a vstupem do existujících detailů. Pravidelně obnovuje uložené
podklady a po změně projektu zahodí předchozí výsledek; pozdní odpověď nesmí
přepsat nový scope. Chyba se zobrazí, starý stav se nevydává za aktuální.
Návrh zlepšení otevře existující editor návrhů; žádný nový model se nespouští.

## Ověření a meze

Regrese pokrývá scope, chybějící přijetí, pracovní rozdíl, aktivní a nahlášený
běh, historickou revizi, samostatné lidské dokončení a nepravdivost automatického
merge/deploy. Browser ověří přehled, detail, mobil a změnu scope. Neprobíhá
produkční migrace, merge PR, automatické přijetí ani placené spuštění.
