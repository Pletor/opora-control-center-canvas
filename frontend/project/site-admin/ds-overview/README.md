# Overview design systému

První sekce Design Systemu ve Správě webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §3): titulek systému (`document.title`), souhrn počtů (témata, barvy, styly, rodiny, fonty, mezery, zaoblení, stíny, komponenty, assety; počet vede do své sekce) a README (`design.readme`, brand book, nejvýš 200 kB) jako markdown editor s náhledem (psát / vedle sebe / náhled).

- `logic/markdown.ts` (+ test): převod markdownu na strom bloků (nadpisy, odstavce, seznamy, citace, kód, oddělovač; v řádku tučné, kurzíva, kód, bezpečné odkazy). Náhled `MarkdownPreview` skládá React prvky, HTML z README se nikdy nevkládá.
- Karty „Začít z…“ (GitHub, srdce, nahrané soubory) a cover přijdou v dalším kroku.

Dílek nic neukládá: titulek a README hlásí `onTitle` / `onReadme` rodiči `SiteAdmin`.
