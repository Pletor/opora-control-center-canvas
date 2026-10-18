import { convertToExcalidrawElements, newElementWith } from "@excalidraw/excalidraw";
import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import type { WireframeKind } from "@/editor/canvas/wireframes/logic/wireframe-model";
import { buildWireframeMetadata, getWireframeTemplate, sanitizeWireframeMetadata } from "@/editor/canvas/wireframes/logic/wireframe-model";
import type { InspectableWireframe } from "@/editor/canvas/wireframes/components/WireframeInspector";

// Prvky wireframu vložené do kresby (rámec bloku, sloupce, popsaný prvek) a jejich podoba pro inspektor.
function labelElement(kind: WireframeKind, x: number, y: number, width: number, height: number, frameId: string | null) {
  const template = getWireframeTemplate(kind);
  const customData = buildWireframeMetadata(kind);
  if (kind === "heading" || kind === "text") {
    return convertToExcalidrawElements([
      { type: "text", x, y, text: template.label, fontSize: kind === "heading" ? 28 : 18, frameId, customData },
    ], { regenerateIds: true });
  }
  return convertToExcalidrawElements([
    {
      type: "rectangle",
      x,
      y,
      width,
      height,
      frameId,
      strokeColor: "#8fb3c9",
      backgroundColor: "transparent",
      roughness: 0,
      label: { text: template.label },
      customData,
    },
  ], { regenerateIds: true });
}

export function insertWireframeElements(kind: WireframeKind, sequence: number, x: number, y: number, parentFrameId: string | null): readonly ExcalidrawElement[] {
  const template = getWireframeTemplate(kind);
  if (template.role === "element") return labelElement(kind, x, y, template.width, template.height, parentFrameId).map((element) => newElementWith(element, { frameId: parentFrameId }));
  const frame = convertToExcalidrawElements([
    {
      type: "frame",
      x,
      y,
      width: template.width,
      height: template.height,
      name: template.label,
      children: [],
      strokeColor: "#7699ae",
      backgroundColor: "transparent",
      customData: buildWireframeMetadata(kind),
    },
  ], { regenerateIds: true });
  const frameId = frame[0]?.id;
  if (!frameId) return frame;
  if (kind === "two-columns" || kind === "three-columns") {
    const slots = template.slots ?? 2;
    const columns = Array.from({ length: slots }, (_, index) => ({
      type: "rectangle" as const,
      x: x + 24 + index * ((template.width - 48) / slots),
      y: y + 62,
      width: (template.width - 48) / slots - 12,
      height: template.height - 86,
      frameId,
      strokeColor: "#526b7a",
      backgroundColor: "transparent",
      roughness: 0,
    }));
    return [...frame, ...convertToExcalidrawElements(columns, { regenerateIds: true })];
  }
  return frame;
}

export function inspectable(element: ExcalidrawElement | null): InspectableWireframe | null {
  if (!element) return null;
  const customData = sanitizeWireframeMetadata(element.customData);
  if (!customData) return null;
  return {
    id: element.id,
    type: element.type,
    ...(element.type === "text" ? { text: element.text } : {}),
    ...(element.type === "frame" || element.type === "magicframe" ? { name: element.name } : {}),
    strokeColor: element.strokeColor,
    backgroundColor: element.backgroundColor,
    metadata: customData.oporaWireframe,
  };
}
