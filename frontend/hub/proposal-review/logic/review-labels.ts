/** Present server evidence clearly without changing its raw API values. */
const riskReasons: Record<string, string> = {
  specification_changed: "Mění se zadání karty a podmínky jejího splnění.",
  graph_addition: "Do plánu přibývají karty nebo vazby.",
  first_graph_manifest_adoption: "Poprvé se schvaluje celý výchozí graf a jeho zadání.",
  graph_changed: "Mění se struktura přijatého plánu.",
  nodes_removed: "Z plánu se odstraňují karty nebo jiné prvky.",
  edges_removed: "Z plánu se odstraňují vazby mezi úkoly.",
  shared_architecture_context_adopted: "Přebírá se změněný sdílený kontext architektury.",
  first_content_manifest_adoption: "Poprvé se schvaluje celý výchozí obsah, nejen viditelné změny.",
  text_changed: "Mění se textový obsah karty.",
  drawing_changed: "Mění se scéna kresby.",
  materials_changed: "Mění se podklady připojené ke kartě.",
  "control_field_changed:actions": "Mění se akce a postupy vykonávání úlohy.",
  "control_field_changed:rules": "Mění se pravidla, kterými se úloha řídí.",
  "control_field_changed:blocks": "Mění se řídicí bloky, jejich větvení nebo porty.",
  "control_field_changed:downloadsUrl": "Mění se příznak, zda úloha stahuje URL.",
};
const blockedReasons: Record<string, string> = {
  "Proposal has a stale accepted parent; rebase it explicitly.": "Návrh má starší přijatý základ. Výslovně jej převeďte na aktuální hlavu.",
  "Open blocking findings require a human resolution.": "Otevřené blokující nálezy musí vypořádat člověk s odůvodněním.",
  "Current human acknowledgement of this proposal, policy and review head is required.": "Chybí aktuální lidské potvrzení přesného návrhu, pravidel a hlavy diskuse.",
};
export const riskReasonLabel = (reason: string) => riskReasons[reason] ?? `Další důvod serveru: ${reason}`;
export const blockedReasonLabel = (reason: string) => blockedReasons[reason] ?? reason;
