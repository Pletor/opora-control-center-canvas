// Kategorie Hooky a commands: ověřovací příkazy, restart serveru po zásahu do backendu a to, co
// řídí Claude Code (backend/claude_code/README.md — katalog skills, hooky a commands přibudou).
// Drop položky vytvoří akci v bloku Akce, stejně jako pipelines.
import type { AgentItem } from "./agent-catalog";

export const hookItems: AgentItem[] = [
  {
    id: "hook-verify-gates",
    category: "hooks",
    label: "Ověřovací příkazy před uložením",
    hint: "uv run pytest backend, npm test, npm run build — spustit a vložit výstup, ne jen tvrdit hotovo.",
    icon: "⌸",
    kind: "action",
    rules: {
      must: [
        "Všechny tři příkazy proběhnou před hlášením hotovo.",
        "Výstup jde do odpovědi, ne jen dojem, že to funguje.",
      ],
      mustNot: [
        "Žádné přeskočení brány kvůli spěchu.",
        "Žádné hotovo s padajícím testem.",
      ],
    },
    decomposition: [
      { title: "Backend", text: "uv run pytest backend." },
      { title: "Frontend", text: "npm test (vitest, bez DOM)." },
      { title: "Sestavení", text: "npm run build (tsc --noEmit + vite build)." },
    ],
    template: [
      "1. uv run pytest backend",
      "2. npm test",
      "3. npm run build",
      "4. Vlož výstup všech tří do hlášení.",
    ].join("\n"),
    endCriteria: "Tři příkazy proběhly bez chyby, výstup je v hlášení.",
    stopCondition: "Některý příkaz selhal — zastav, řekni který a proč, neoznačuj úkol za hotový.",
    refs: ["test-done-gates"],
  },
  {
    id: "hook-restart-backend",
    category: "hooks",
    label: "Restart backendu po změně",
    hint: "uv run opora na 8740 nehotreloaduje Python; po zásahu do backend/ je potřeba restart.",
    icon: "⟲",
    kind: "action",
    rules: {
      must: [
        "Po každé změně v backend/ se server restartuje, než se ověřuje chování v aplikaci.",
        "Restart se dělá stejným příkazem (uv run opora), ne ručním obcházením portu.",
      ],
      mustNot: [
        "Žádné spoléhání, že se změna v Pythonu projeví bez restartu.",
        "Žádná druhá instance serveru paralelně na stejném portu.",
      ],
    },
    decomposition: [
      { title: "Detekce", text: "Změna souboru pod backend/ mimo čistá data." },
      { title: "Restart", text: "Zastavit běžící uv run opora a spustit znovu." },
      { title: "Ověření", text: "Až po restartu ověřovat chování přes API nebo UI." },
    ],
    template: [
      "1. Ulož změnu v backend/.",
      "2. Zastav běžící uv run opora (port 8740).",
      "3. Spusť uv run opora znovu.",
      "4. Teprve pak ověřuj chování přes API nebo UI.",
    ].join("\n"),
    endCriteria: "Server běží s novým kódem; endpoint vrací chování odpovídající poslední změně.",
    stopCondition: "Endpoint pořád vrací staré chování po uložení — zastav, zkontroluj, jestli restart proběhl, neladí se duch starého procesu.",
    refs: [],
  },
  {
    id: "hook-pre-save-lock",
    category: "hooks",
    label: "Zámek a CAS revize při uložení",
    hint: "Každý zápis na kartu nese expectedRevision; server zapisuje pod zámkem grafu, kolize je 409.",
    icon: "⚷",
    kind: "action",
    rules: {
      must: [
        "Zápis čte revizi před uložením a posílá ji zpátky jako expectedRevision.",
        "Server zapisuje pod zámkem grafu, aby se souběžné zápisy neprolnuly.",
      ],
      mustNot: [
        "Žádný zápis bez revize.",
        "Žádné tiché přepsání při 409 — musí se načíst znovu a sloučit.",
      ],
    },
    decomposition: [
      { title: "Čtení", text: "GET vrátí obsah i revision." },
      { title: "Zápis", text: "POST s expectedRevision." },
      { title: "Kolize", text: "409 → načti znovu, zopakuj zápis s novou revizí." },
    ],
    template: [
      "1. GET aktuální stav a revision.",
      "2. Priprav patch.",
      "3. POST s expectedRevision.",
      "4. Při 409 znovu GET a zopakuj s aktuální revizí.",
    ].join("\n"),
    endCriteria: "Zápis proběhl s revizí odpovídající poslednímu čtení; žádná ztracená změna.",
    stopCondition: "Opakovaná 409 kolize — zastav, zjisti, kdo jinak zapisuje, neposílej zápis silou.",
    refs: ["be-cas-revision"],
  },
  {
    id: "hook-claude-code-commands",
    category: "hooks",
    label: "Claude Code: commands, hooky a skills projektu",
    hint: "backend/claude_code čte SKILL.md z .claude/skills projektu, uživatele a pluginů; hooky a commands přibudou.",
    icon: "⌘",
    kind: "action",
    rules: {
      must: [
        "Skills se čtou z .claude/skills projektu, ~/.claude/skills a marketplace pluginů — katalog jen čte, nic nespouští.",
        "Vypnuté skills se drží v jednom JSON v datovém kořeni projektu.",
      ],
      mustNot: [
        "Žádné spouštění skillu z aplikace — jen výpis a přepínání zapnuto/vypnuto.",
        "Žádný zápis do .claude/skills mimo projekt uživatele.",
      ],
    },
    decomposition: [
      { title: "Katalog", text: "skills_catalog.py sesbírá SKILL.md ze tří zdrojů." },
      { title: "Preference", text: "skill_preferences.py drží, co je vypnuté." },
      { title: "Budoucnost", text: "Hooky a commands (.claude/hooks, .claude/commands) přibudou stejnou cestou." },
    ],
    template: [
      "1. Přečti SKILL.md kandidáta (projekt / uživatel / plugin).",
      "2. Zapiš do katalogu jméno, popis a zdroj.",
      "3. Respektuj skill_preferences (vypnuto = nenabízet).",
    ].join("\n"),
    endCriteria: "Katalog skills odpovídá tomu, co je na disku, a respektuje vypnuté položky.",
    stopCondition: "Skill by se měl spustit z aplikace samotné — to je mimo hranice, zastav.",
    refs: [],
  },
];
