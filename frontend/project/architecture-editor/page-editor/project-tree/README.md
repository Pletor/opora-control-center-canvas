# Strom projektu

Levý panel Editoru stránky. Projekce grafu (`productTree`): skupiny prostředí *Produkce · LIVE* (zelená), *Vývoj · DEV* (jantarová), další pojmenovaná prostředí a *Sdílená struktura* (vícehostové aplikace), v nich domény (ikona druhu, host, „druh · účel“) a pod nimi stránky s odsazenými podstránkami. Aktivní stránka je zvýrazněná, skupina s aktivní doménou je otevřená.

Strom jen naviguje: klik na stránku hlásí `onOpenPage(domainId, pageId)`, „+ Stránka“ hlásí `onAddPage(domainId)` a rodič přepne na Mapu projektu. Model je v `logic/project-tree-model.ts` s testem vedle.
