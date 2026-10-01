/**
 * Otázky k rozhodnutí ve tvaru, který vrací skill grilling:
 *
 *   ❓ **Q1** - **K čemu PDF slouží**: Kdo ho čte a co s ním udělá? Možnosti: (a) …
 *
 *   ➡️ (a), sdílení přehledu s lidmi mimo aplikaci. Z toho plyne…
 *
 * Projde i `---` mezi otázkami, pomlčka `-`, `–` nebo `—`, `Q1.` bez tučného písma a otázka bez ❓.
 * Výsledek je úvodní text, otázky a závěrečný text; žádný text se neztratí. Když se nenajdou aspoň dvě
 * otázky, vrací null a odpověď se vykreslí jako běžný Markdown. Uvnitř bloku kódu se nehledá.
 */

export type Decision = { id: string; topic: string; question: string; recommendation: string };

export type DecisionSet = { intro: string; questions: Decision[]; outro: string };

// nadpis a ❓ (volitelně) · Q<n> (volitelně tučně, i „**Q1.**“) · oddělovač . : ) nebo pomlčka · zbytek řádku
const QUESTION = /^\s*(?:#{1,6}\s+)?(?:❓️?\s*)?(?:\*\*)?Q(\d{1,2})(?:\*\*)?(?:\s*[.:)](?:\*\*)?|\s+[-–—])\s*(?:[-–—]\s*)?(.*)$/;
const RECOMMENDATION = /^\s*(?:➡️?|→)\s*(?:\*\*Doporučení:?\*\*:?\s*|Doporučení:\s*)?(.*)$/;
const RULE = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
const FENCE = /^\s*```/;

/** Téma a otázka z řádku za „Q1 -“: „**Téma**: otázka“, „Téma: otázka“, jinak celé jako otázka. */
function splitHead(rest: string): { topic: string; question: string } {
  const bold = rest.match(/^\*\*(.+?)\*\*\s*:?\s*(.*)$/);
  if (bold) return { topic: bold[1].replace(/:\s*$/, "").trim(), question: bold[2].trim() };
  const plain = rest.match(/^([^:?.!]{1,80}):\s+(.*)$/);
  if (plain) return { topic: plain[1].trim(), question: plain[2].trim() };
  return { topic: "", question: rest.trim() };
}

/** Odřízne prázdné řádky a oddělovače `---` na okrajích. */
function trimBlock(lines: string[]): string {
  let start = 0;
  let end = lines.length;
  while (start < end && (!lines[start].trim() || RULE.test(lines[start]))) start++;
  while (end > start && (!lines[end - 1].trim() || RULE.test(lines[end - 1]))) end--;
  return lines.slice(start, end).join("\n");
}

type Draft = { id: string; topic: string; question: string[]; recommendation: string[]; after: string[]; phase: "question" | "recommendation" | "after" };

export function parseDecisions(text: string): DecisionSet | null {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const intro: string[] = [];
  const drafts: Draft[] = [];
  let fenced = false;

  for (const line of lines) {
    const current = drafts[drafts.length - 1];
    if (FENCE.test(line)) fenced = !fenced;
    const question = fenced ? null : line.match(QUESTION);
    if (question) {
      const head = splitHead(question[2]);
      drafts.push({ id: `Q${Number(question[1])}`, topic: head.topic, question: head.question ? [head.question] : [], recommendation: [], after: [], phase: "question" });
      continue;
    }
    if (!current) { intro.push(line); continue; }
    const recommendation = fenced ? null : line.match(RECOMMENDATION);
    if (recommendation && current.phase === "question") {
      current.phase = "recommendation";
      current.recommendation.push(recommendation[1]);
      continue;
    }
    if (current.phase === "recommendation" && (!line.trim() || RULE.test(line))) current.phase = "after";
    if (current.phase === "question") current.question.push(line);
    else if (current.phase === "recommendation") current.recommendation.push(line);
    else current.after.push(line);
  }

  if (drafts.length < 2) return null;
  const last = drafts.length - 1;
  const questions = drafts.map((d, i) => {
    // Text mezi doporučením a další otázkou patří k doporučení, aby se neztratil; za poslední otázkou je to závěr.
    const extra = i < last ? trimBlock(d.after) : "";
    const recommendation = [trimBlock(d.recommendation), extra].filter(Boolean).join("\n\n");
    return { id: d.id, topic: d.topic, question: trimBlock(d.question), recommendation };
  });
  if (questions.some((q) => !q.question && !q.topic)) return null;
  return { intro: trimBlock(intro), questions, outro: trimBlock(drafts[last].after) };
}
