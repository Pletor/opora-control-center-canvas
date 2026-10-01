// Verdikt Oracle nad jedním uzlem: smí se to commitnout, smí to do mainu, a co chybí, když ne.
// Čisté funkce nad `docs/synchronizace-pravdy.md`, části 4, 5 a 8; žádná síť, žádné ukládání —
// report a nodeId dostává hotové ten, kdo dílek skládá.

// Tvar odpovědi drží backend; typy žijí na jednom místě vedle klienta API.
import type { SyncCheck, SyncReport, SyncVerdict } from "@/shared/desktop-state/logic/types";

export type { SyncCheck, SyncReport, SyncVerdict };

export type BadgeTone = "green" | "amber" | "red" | "muted";

export type BadgeView = { tone: BadgeTone; label: string; detail: string; steps: string[]; checks: SyncCheck[] };

/** Verdikt uzlu z hotového reportu; `null`, když report, uzel nebo jeho verdikt v reportu chybí. */
export function pickVerdict(report: SyncReport | null, nodeId: string | null): SyncVerdict | null {
  if (!report || !nodeId) return null;
  return report.verdicts.find((verdict) => verdict.scope.kind === "node" && verdict.scope.id === nodeId) ?? null;
}

// Český tvar podle počtu neprošlých kontrol: 1 → jednotné číslo, 2 až 4 → málo, 5 a víc → řadové s rodem střed.
function failedChecksLabel(count: number): string {
  if (count === 1) return "Neprošla 1 kontrola.";
  if (count >= 2 && count <= 4) return `Neprošly ${count} kontroly.`;
  return `Neprošlo ${count} kontrol.`;
}

/** Popisek, tón a detail štítku pro daný verdikt; `null`, když verdikt chybí. */
export function badgeView(verdict: SyncVerdict | null): BadgeView | null {
  if (!verdict) return null;
  const { checks, nextSteps, blocking } = verdict;
  let tone: BadgeTone;
  let label: string;
  let detail: string;
  switch (verdict.state) {
    case "green":
      tone = "green";
      label = "Zelené";
      detail = "Zadání, kód, testy a důkaz sedí.";
      break;
    case "waiting": {
      const failed = checks.filter((check) => !check.passed).length;
      tone = "amber";
      label = "Čeká na 1:1";
      detail = failed > 0 ? failedChecksLabel(failed) : "Čeká na výsledek kontrol.";
      break;
    }
    case "closed":
      tone = "muted";
      label = "Uzavřeno";
      detail = "Nehýbe se s ní; zápisy se odmítají.";
      break;
    default:
      tone = "muted";
      label = "Rozpracováno";
      detail = "Práce běží.";
  }
  // Uzavřený rozsah má canCommit i canMerge vždy nepravda, ale žádné blokující echo (`blocking`
  // je prázdné) — to není zákaz commitu, jen zámek. Červený tón patří jen skutečnému vysokému echu.
  if (!verdict.canMerge && !verdict.canCommit && blocking.length > 0) {
    tone = "red";
    label = "Nesmí se commitnout";
  }
  return { tone, label, detail, steps: nextSteps, checks };
}
