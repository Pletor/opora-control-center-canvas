"""Project a research digest into addressable alternatives without claiming approval."""
import json


def operations(result, fragment, topic, refs, at, stable_id):
    # OP-6FF3AC.1: comparisons must be readable as cards, not buried in one digest.
    root = stable_id("rc_", fragment, "result")
    facts = {fact.get("id"): (stable_id("rc_", fragment, "fact", i, fact.get("id")), fact)
             for i, fact in enumerate(result["facts"])}
    output = []
    for layer, comparison in result["digest"].get("layers", {}).items():
        for index, option in enumerate(comparison.get("options", [])):
            ident = stable_id("rc_", fragment, "option", layer, index)
            title = option.get("approach") or "Varianta vyžadující doplnění"
            content = {"option": option, "recommended": comparison.get("recommended", ""),
                       "risks": comparison.get("risks", []),
                       "hypotheses": result["digest"].get("hypotheses", []),
                       "approval": "Návrh syntézy; přijetí člověkem ani zadání tím nevzniká."}
            output.append({"op": "card", "id": ident, "expectedRevision": 0, "kind": "option",
                           "title": title[:500], "summary": title[:4000], "topicPath": [*topic, layer],
                           "content": json.dumps(content, ensure_ascii=False, indent=2), "status": "open",
                           "verification": {"status": "inference", "method": "research_digest", "at": at},
                           "sources": [], "refs": refs})
            output.append(edge(stable_id, ident, root, "option_for",
                               "Varianta z porovnání výzkumu; výhody, nevýhody a omezení jsou v detailu.", []))
            for fact_id in dict.fromkeys(option.get("facts", [])):
                if fact_id not in facts:
                    continue  # Unknown evidence stays visible in the raw comparison, never an invented link.
                evidence_id, fact = facts[fact_id]
                verified = fact.get("verified") in ("verified", "observed") and fact.get("kind", "fact") == "fact"
                output.append(edge(stable_id, evidence_id, ident, "supports" if verified else "elaborates",
                                   "Syntéza přiřadila tento podklad k variantě; rozsah tvrzení a ověření je v detailu podkladu.",
                                   [evidence_id]))
    return output


def edge(stable_id, source, target, relation, reason, evidence):
    return {"op": "edge", "id": stable_id("re_", source, target), "expectedRevision": 0,
            "fromId": source, "toId": target, "relation": relation, "reason": reason,
            "resolved": "", "missing": "", "evidenceIds": evidence}
