/** Prohlížeč určuje dvojklik přes detail, nikoli náš odhad systémového intervalu. */
export function cardClickAction(event: { detail: number; excluded?: boolean; modified?: boolean }): "ignore" | "preview" | "enter" {
  if (event.excluded || event.modified) return "ignore";
  return event.detail === 2 ? "enter" : event.detail <= 1 ? "preview" : "ignore";
}

/** Blok, port a ovládací prvky mají vlastní akci; náhled na ně nesmí reagovat. */
export function isCardControl(target: { closest: (selector: string) => unknown } | null): boolean {
  return !!target?.closest("[data-block-id], .react-flow__handle, .node-card__port, .node-card__port-label, button, input, textarea, select, a, summary, [role=button]");
}

/** Náhled nebere hit target původní kartě. Modalita začne až mimo ni nebo klávesnicí. */
export function shouldActivateDialog(rect: { left: number; top: number; right: number; bottom: number }, point: { x: number; y: number }): boolean {
  return point.x < rect.left || point.x > rect.right || point.y < rect.top || point.y > rect.bottom;
}
