# Rešerše jako podklad nativního předání úkolu

Návaznost při importu připíná skutečné revize a digesty karet a hran komponenty dané otázky, včetně již uložených odkazovaných zjištění. Jiná otázka je hranice průchodu; její podklady se nepřibírají jen přes společnou hranu. Pin uchovává citace, jejich metadata a stav ověření uvnitř revize karty. Pin sám tvrzení neověřuje ani neschvaluje.

Přijaté nativní návrhy nesou `researchSource`. Při přípravě úkolu se jejich skutečně změněné uzly, konce změněných hran a vlastníci dokumentů/stavu protnou s existujícím výběrem `select_scope`. Nejnovější přijatý zdroj stejné otázky pro stejný uzel nahradí starší; nesouvisející přijatá změna původní podklad nevymaže. První `canvas-plan` dokládá dokončený scoped receipt autora `agent/heart`, původní `acceptedHeadAtWrite:null`, shodnou identitu návaznosti a skutečné dotčené uzly. Uzel musí následně existovat v přijatém nativním manifestu. Receipt není lidské přijetí.

Nová předání mají `researchEvidence` v neměnném assignmentu a v autentizovaném kontextovém tokenu. Kontrola heartbeat/výsledku ověřuje právě tyto piny; monotónní revize odhalí i změnu a následné vrácení, archivaci a obnovení. Historické assignmenty ani výsledky se nepřepisují. Dotčený výsledek dostane odvozené `staleEvidence`; nesouvisející uzavřený úkol nezastará jen posunem přijaté hlavy jinde. Nový research-derived claim vyžaduje připravený kontext verze 2. Již vydané staré kontexty mají explicitní `legacy-untracked` pokrytí, bez domyšlených zpětných pinů.

Stejné podklady se znovu kontrolují při vytvoření a lidském přijetí návrhu. Známá změna zjištění proto nedovolí přijmout zastaralý návrh a až potom selhat při převzetí práce.

## Původní zadání a hranice pokrytí

Sémantický vstup původní rešerše zachycuje `title`, `text`, `kind`, `parent_id`, `scope_node_id`, `discipline`, `deleted` a `details.research.question`. Všechny následující revize se porovnávají s tímto vstupem, takže změna a vrácení otázky nezmizí. Běžný stav běhu, číslo kola a výstupní `verdict`, `confidence`, `approach`, `evidence` nejsou vstupní zadání. Import mapy a pozdější `research-update` jsou dvě operace; tento mechanismus netvrdí jejich společnou atomicitu.

Nový příkaz `research` ukládá do importního intentu `finalization` s přesným zamýšleným `status:done`, `verdict`, `confidence`, `approach` a `evidence`. Návaznost zůstane `awaiting_finalization`, dokud existující HeartDriver v nativní historii nezpozoruje přesně tento dokončený výstup. Teprve pak připne jeho skutečnou `detailsRevision` a digest výstupních polí a povolí plánování. Změna kteréhokoli z těchto výstupních polí i následné vrácení zneplatní dotčené předání; změna pouze stavu běhu nebo čísla kola výstupní pin nemění. Piny mají `originalSourceCoverage: semantic-input-and-observed-completed-output`.

Pád po importu před dokončením nechá trvalé čekání bez spotřeby LLM pokusu. Pád po dokončení před pozorováním neztratí výsledek, protože se čte nativní neměnná historie. Jiný dokončený výstup nebo změna po správném dokončení před pozorováním vyústí v konflikt, nikoli v přijetí posledních dostupných hodnot. Příkaz `research-map import --file ...` používá uložený intent: nejprve načte původní revizi, zapíše dokončení pouze s původním CAS, a po posunu revize smí jen ověřit přesný již uložený výsledek. Ztracená odpověď nevede k druhé revizi ani k novému výzkumu.

Starší návaznosti bez dokončovacího intentu si ponechávají výslovné `semantic-input-only; direct-original-output-edits-untracked` pokrytí; starší návaznosti bez evidence mají `legacy-question-only`. Jejich výstupy se zpětně neprohlašují za ověřeně dokončené a stará předání se nepřepisují.

Neexistuje nová fronta, zámek práce ani alternativní úkol. Používají se původní leases, epochy, execution receipts, accepted revisions a immutable assignments.
