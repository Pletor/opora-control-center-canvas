import { expect, it } from "vitest";
import { noteBlocks } from "./note-markdown";

it("reads headings, bullets, paragraphs, bold and code of a sticky note", () => {
  expect(noteBlocks("# Workflow 1 — Ingest\n\n## Krok\n- načti **soubor**\nPoužij `embedding` model.\n#### víc")).toEqual([
    { kind: "heading", level: 1, inline: [{ text: "Workflow 1 — Ingest" }] },
    { kind: "heading", level: 2, inline: [{ text: "Krok" }] },
    { kind: "item", inline: [{ text: "načti " }, { text: "soubor", strong: true }] },
    { kind: "paragraph", inline: [{ text: "Použij " }, { text: "embedding", code: true }, { text: " model." }] },
    { kind: "paragraph", inline: [{ text: "#### víc" }] },
  ]);
});
