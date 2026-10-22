// `@coldtea/pr-lens-renderer` importuje `node:crypto` jen v manifest.js (hash obsahu pro renderAll).
// Prohlížeč volá jen `render`, takže sem nic nedojde; kdyby ano, ať to selže nahlas, ne potichu.
export function createHash(): never {
  throw new Error("node:crypto není v prohlížeči; Lens volá jen render().");
}
