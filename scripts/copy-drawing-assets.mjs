import { cpSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
const source = resolve("node_modules/@excalidraw/excalidraw/dist/prod/fonts");
const destination = resolve("dist/drawing-assets/fonts");
mkdirSync(destination, { recursive: true });
cpSync(source, destination, { recursive: true });
console.log("Drawing fonts copied locally; runtime CDN is not required.");
