# Reconciliation kritiky, 2026-09-09

Původní `synthesis-critic.json` je zachován beze změny. Oba návrhové blockery byly přijaty:

1. Dodatečný kontext: resources mimo původní hashovaný manifest se nepředají pod starým grantem. Nový bundle vyžaduje nový ApprovalGrant, immutable binding a epoch; rebind stejné session jen s prokázanou podporou v čekajícím checkpointu, jinak potvrzený stop a nový run. Již schválené resources lze líně načíst bez změny bundle, vždy s kontrolou při doručení.
2. Import codebase: přidaný R00 a autoritativní read-only cesta od repo/SHA přes inventář a SourceRef až k návrhu mapování, lidskému přijetí a reconcile. Prázdný projekt onboarding přeskočí, existující codebase nikoli. Import nespouští kód a nedělá z neúplné analýzy úplné pokrytí.

Změny jsou pouze v návrhových dokumentech. Nejde o implementované opravy běžícího Canvasu ani důkaz konkrétního CLI adapteru. Finální znovuověření je samostatné review.
