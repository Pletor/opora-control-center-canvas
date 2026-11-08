/** Jedna řádka nad rozhovorem: otevřená otázka Pletora pro srdce a zda je ve frontě, nebo zodpovězená. */
export default function PletorQuestionLine({ text }: { text: string }) {
  if (!text) return null;
  return <p className="pletor__question" role="status">{text}</p>;
}
