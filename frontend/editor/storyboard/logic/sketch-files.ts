// PNG soubory skic bez Reactu: vyrenderuje snímek momentu, nahraje PNG jako obrázek kresby (`/api/drawing-file`)
// a vrátí jeho `fileId` (SHA-1 obsahu, stejné PNG se nezdvojí). Prohlížečové API (canvas, FileReader) jen v těchto funkcích.
import { api } from "@/shared/types/logic/types";
import type { AnimationDef } from "./animations";
import { paintLayers, defaultVisible } from "./storyboard-layout";
import { stateAt, type Storyboard } from "./storyboard-model";

/** Hex SHA-1 řetězce; platné `fileId` backendu (`[A-Za-z0-9_-]{1,120}`). */
export async function fileIdOf(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function blobToDataURL(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Obrázek se nepodařilo přečíst."));
    reader.readAsDataURL(blob);
  });
}

/** Snímek animace v čase `t` se všemi vrstvami animace, bez skici a bez anotací, v rozměru plátna storyboardu. */
export function renderFrameBlob(board: Storyboard, animation: AnimationDef, t: number): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = board.size.w;
  canvas.height = board.size.h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.reject(new Error("Plátno snímku není k dispozici."));
  animation.paint(ctx, canvas.width, canvas.height, stateAt(board, animation, t), t, board, paintLayers(defaultVisible(animation)));
  return new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Snímek se nepodařilo převést na PNG."))), "image/png"));
}

/** Nahraje obrázek (PNG, JPEG, WebP) jako obrázek kresby projektu a vrátí jeho `fileId` (SHA-1 dataURL, stejný obrázek se nezdvojí). */
export async function uploadImage(project: string, workspace: string, blob: Blob, mimeType: string): Promise<string> {
  const dataURL = await blobToDataURL(blob);
  const id = await fileIdOf(dataURL);
  await api("/api/drawing-file", { project, workspace, file: { id, mimeType, dataURL } });
  return id;
}

/** Nahraje PNG jako obrázek kresby projektu a vrátí jeho `fileId`. */
export function uploadPng(project: string, workspace: string, blob: Blob): Promise<string> {
  return uploadImage(project, workspace, blob, "image/png");
}
