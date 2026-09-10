import { cpSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { createRequire } from "node:module";
// Node najde i nadřazené node_modules; veřejný vstup nevyžaduje export package.json.
const require = createRequire(import.meta.url);
const source = resolve(dirname(require.resolve("@excalidraw/excalidraw")), "fonts");
const destination = resolve("dist/drawing-assets/fonts");
mkdirSync(destination, { recursive: true });
cpSync(source, destination, { recursive: true });
console.log("Drawing fonts copied locally; runtime CDN is not required.");
