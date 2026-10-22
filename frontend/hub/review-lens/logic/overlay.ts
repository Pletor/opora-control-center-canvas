// Geometrie plátna Lens. Renderer vrací ke každému obrázku atlas: rámečky pruhů, karet, hran a kroků
// toků v jednotkách viewBoxu SVG. Obrázek se kreslí v měřítku `scale`, takže jednotka viewBoxu je
// `scale` pixelů a překryv (výběr, okraj kroku průvodce) se přepočítá stejně: nic se neměří z pixelů.
export type Box = { x: number; y: number; width: number; height: number };
export type Camera = { scale: number; x: number; y: number };
export type Size = { width: number; height: number };

export const MIN_SCALE = 0.25, MAX_SCALE = 4;
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

/** Rámeček atlasu → absolutní pozice prvku překryvu v pixelech obrázku. */
export function boxStyle(box: Box, scale: number, pad = 0) {
  return { left: (box.x - pad) * scale, top: (box.y - pad) * scale, width: (box.width + 2 * pad) * scale, height: (box.height + 2 * pad) * scale };
}

/** Obal několika rámečků (krok průvodce může mířit na víc prvků); hrana s nulovou šířkou je platná. */
export function unionBox(boxes: readonly Box[]): Box | null {
  if (!boxes.length) return null;
  const left = Math.min(...boxes.map(box => box.x)), top = Math.min(...boxes.map(box => box.y));
  const right = Math.max(...boxes.map(box => box.x + box.width)), bottom = Math.max(...boxes.map(box => box.y + box.height));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/** Kamera, která ukáže rámeček celý a uprostřed výřezu (s okrajem), v mezích přiblížení. */
export function fitCamera(box: Box, viewport: Size, margin = 24, maxScale = 1.6): Camera {
  const width = Math.max(box.width, 1), height = Math.max(box.height, 1);
  const scale = clamp(Math.min((viewport.width - 2 * margin) / width, (viewport.height - 2 * margin) / height), MIN_SCALE, maxScale);
  return { scale, x: viewport.width / 2 - (box.x + width / 2) * scale, y: viewport.height / 2 - (box.y + height / 2) * scale };
}

/** Přiblížení kolem bodu výřezu (kolečko myši, tlačítka ±): bod pod kurzorem zůstane na místě. */
export function zoomAt(camera: Camera, factor: number, point: { x: number; y: number }): Camera {
  const scale = clamp(camera.scale * factor, MIN_SCALE, MAX_SCALE);
  const ratio = scale / camera.scale;
  return { scale, x: point.x - (point.x - camera.x) * ratio, y: point.y - (point.y - camera.y) * ratio };
}

/** Posun tažením. */
export const panBy = (camera: Camera, dx: number, dy: number): Camera => ({ ...camera, x: camera.x + dx, y: camera.y + dy });
