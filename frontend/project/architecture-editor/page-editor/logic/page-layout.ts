// Které sloupce Editoru stránky jsou otevřené. Šířku okna řeší CSS (media queries); tady se jen
// skládají BEM varianty, aby styl věděl, co zobrazit a co při úzkém okně schovat.
export type PageFocus = "map" | "structure";
export type PageColumns = { structure: boolean; detail: boolean; focus: PageFocus };

/** Varianty bloku `page-editor`: otevřený hierarchický editor, otevřený detail, co má přednost na úzkém okně. */
export function pageLayoutClass({ structure, detail, focus }: PageColumns): string {
  return ["page-editor",
    structure && "page-editor--structure",
    detail && "page-editor--detail",
    structure && `page-editor--focus-${focus}`,
  ].filter(Boolean).join(" ");
}
