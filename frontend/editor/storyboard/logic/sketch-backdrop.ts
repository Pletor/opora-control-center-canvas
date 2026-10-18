// Podklad skici momentu bez Reactu: do Excalidraw kresby se pod skicu vloží snímek animace (zamčený) a skica předchozího
// momentu (průhledná, onion-skin). Podkladové prvky nesou `customData.storyboardBackdrop` a mají pevné id, takže se při
// dalším otevření vymění za čerstvé. Chybějící pole prvků (verze, seed…) doplní `restoreElements` v kresbě.
import type { Moment } from "./storyboard-model";

export const BACKDROP_KEY = "storyboardBackdrop";
const FRAME_ID = "sb-backdrop-frame";
const PREV_ID = "sb-backdrop-prev";

type Loose = { id?: string; customData?: Record<string, unknown> | null };
export type BackdropElement = {
  type: "image"; id: string; fileId: string; status: "saved"; scale: [number, number];
  x: number; y: number; width: number; height: number; angle: 0; opacity: number; locked: boolean;
  customData: { storyboardBackdrop: true };
};

/** Vrstva kresby ve tvaru z kontraktu: `sb/<nodeId>/<momentId>`. */
export const sketchLayer = (nodeId: string, momentId: string) => `sb/${nodeId}/${momentId}`;

export const isBackdrop = (element: Loose) => element.customData?.[BACKDROP_KEY] === true;

function image(id: string, fileId: string, width: number, height: number, opacity: number, locked: boolean): BackdropElement {
  return { type: "image", id, fileId, status: "saved", scale: [1, 1], x: 0, y: 0, width, height, angle: 0, opacity, locked, customData: { [BACKDROP_KEY]: true } };
}

/** Snímek animace (zamčený, plný) a předchozí skica (30 %), pokud existuje. Snímek je dole, skica nad ním. */
export function backdropElements({ frameFileId, prevSketchFileId, width, height }: {
  frameFileId: string; prevSketchFileId?: string | null; width: number; height: number;
}): BackdropElement[] {
  const out = [image(FRAME_ID, frameFileId, width, height, 100, true)];
  if (prevSketchFileId) out.push(image(PREV_ID, prevSketchFileId, width, height, 30, true));
  return out;
}

/** Scéna bez podkladových prvků. */
export function stripBackdrop<T extends Loose>(elements: readonly T[]): T[] {
  return elements.filter((element) => !isBackdrop(element));
}

/** Čerstvý podklad pod uloženou scénou: starý podklad pryč, nový na začátek (tedy dole). */
export function withFreshBackdrop<T extends Loose, B extends Loose>(elements: readonly T[], backdrop: readonly B[]): (T | B)[] {
  return [...backdrop, ...stripBackdrop(elements)];
}

/** `fileId` skici nejbližšího předchozího momentu, který nějakou má; jinak null. */
export function previousSketchFileId(moments: readonly Pick<Moment, "sketch">[], index: number): string | null {
  for (let i = index - 1; i >= 0; i--) {
    const fileId = moments[i]?.sketch?.fileId;
    if (fileId) return fileId;
  }
  return null;
}
