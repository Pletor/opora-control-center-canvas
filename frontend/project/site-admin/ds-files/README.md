# Files design systému

Sekce Files Správy webu: odkazy na odvozené soubory `tokens.css`, `tokens.json` a `README.md` (`GET /api/site-admin/<soubor>?project=`), které server generuje z uložené revize (kontrakt Správy webu §2). Dílek dostane adresy, revizi a příznak neuložených změn od rodiče a jen je zobrazí. Strom souborů s assety a fonty přijde s Assets v dalším kroku.
