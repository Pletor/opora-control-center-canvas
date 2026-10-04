// Uložený pohled mapy (x, y, zoom) může po změně obsahu nebo okna schovat část karet.
// Tahle čistá funkce řekne, zda pohled ukazuje každou kartu aspoň částí; jinak mapa přiblíží vše (fitView).
export type ViewportLike = { x: number; y: number; zoom: number };
export type Box = { x: number; y: number; w: number; h: number };

/** Zasahuje každý box (v souřadnicích mapy) do plochy `width` × `height` při daném pohledu? Prázdná mapa se bere jako v pořádku. */
export function viewportShowsAllNodes(viewport: ViewportLike, size: { width: number; height: number }, boxes: Box[]): boolean {
  return boxes.every((box) => {
    const left = box.x * viewport.zoom + viewport.x;
    const top = box.y * viewport.zoom + viewport.y;
    return left < size.width && left + box.w * viewport.zoom > 0 && top < size.height && top + box.h * viewport.zoom > 0;
  });
}
