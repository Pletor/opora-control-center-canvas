// Ikony karet Studia převzaté z prototypu Architektura projektu (`prototype/icons.mjs`), který je generoval z Lucide.
// Lucide Icons, ISC License, Copyright (c) 2026 Lucide Icons and Contributors; ikona `monitor` pochází z Feather
// (MIT, Copyright (c) 2013-present Cole Bemis). Plné znění licence: `../LUCIDE-LICENSE`.
// Tvar je seznam prvků SVG (značka + atributy), aby je React vykreslil bez vkládání HTML.

export type IconShape = ["path", { d: string }] | ["circle", { cx: number; cy: number; r: number }]
  | ["rect", { width: number; height: number; x: number; y: number; rx: number }] | ["line", { x1: number; x2: number; y1: number; y2: number }]
  | ["ellipse", { cx: number; cy: number; rx: number; ry: number }];
export type StudioIconName = "globe" | "layout-dashboard" | "list-ordered" | "box" | "monitor" | "server-cog" | "database-zap" | "workflow";

export const STUDIO_ICONS: Record<StudioIconName, IconShape[]> = {
  globe: [["circle", { cx: 12, cy: 12, r: 10 }], ["path", { d: "M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" }], ["path", { d: "M2 12h20" }]],
  "layout-dashboard": [
    ["rect", { width: 7, height: 9, x: 3, y: 3, rx: 1 }], ["rect", { width: 7, height: 5, x: 14, y: 3, rx: 1 }],
    ["rect", { width: 7, height: 9, x: 14, y: 12, rx: 1 }], ["rect", { width: 7, height: 5, x: 3, y: 16, rx: 1 }],
  ],
  "list-ordered": [
    ["path", { d: "M11 5h10" }], ["path", { d: "M11 12h10" }], ["path", { d: "M11 19h10" }], ["path", { d: "M4 4h1v5" }], ["path", { d: "M4 9h2" }],
    ["path", { d: "M6.5 20H3.4c0-1 2.6-1.925 2.6-3.5a1.5 1.5 0 0 0-2.6-1.02" }],
  ],
  box: [
    ["path", { d: "M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" }],
    ["path", { d: "m3.3 7 8.7 5 8.7-5" }], ["path", { d: "M12 22V12" }],
  ],
  monitor: [["rect", { width: 20, height: 14, x: 2, y: 3, rx: 2 }], ["line", { x1: 8, x2: 16, y1: 21, y2: 21 }], ["line", { x1: 12, x2: 12, y1: 17, y2: 21 }]],
  "server-cog": [
    ["path", { d: "m10.852 14.772-.383.923" }], ["path", { d: "M13.148 14.772a3 3 0 1 0-2.296-5.544l-.383-.923" }], ["path", { d: "m13.148 9.228.383-.923" }],
    ["path", { d: "m13.53 15.696-.382-.924a3 3 0 1 1-2.296-5.544" }], ["path", { d: "m14.772 10.852.923-.383" }], ["path", { d: "m14.772 13.148.923.383" }],
    ["path", { d: "M4.5 10H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-.5" }],
    ["path", { d: "M4.5 14H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2h-.5" }],
    ["path", { d: "M6 18h.01" }], ["path", { d: "M6 6h.01" }], ["path", { d: "m9.228 10.852-.923-.383" }], ["path", { d: "m9.228 13.148-.923.383" }],
  ],
  "database-zap": [
    ["ellipse", { cx: 12, cy: 5, rx: 9, ry: 3 }], ["path", { d: "M3 5V19A9 3 0 0 0 15 21.84" }], ["path", { d: "M21 5V8" }],
    ["path", { d: "M21 12L18 17H22L19 22" }], ["path", { d: "M3 12A9 3 0 0 0 14.59 14.87" }],
  ],
  workflow: [["rect", { width: 8, height: 8, x: 3, y: 3, rx: 2 }], ["path", { d: "M7 11v4a2 2 0 0 0 2 2h4" }], ["rect", { width: 8, height: 8, x: 13, y: 13, rx: 2 }]],
};
