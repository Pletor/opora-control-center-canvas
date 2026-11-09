"""Factual comparison of native specifications and references, without generated conclusions."""
import json
from backend.brain_opora.determinism.milestone_lineage import input_closure


def facts(item):
    nodes = {node["id"]: node for node in item["view"]["graph"]["nodes"]}
    _, _, edges = input_closure(item["view"]["graph"], [item["node"]["id"]])
    inputs = [{"nodeId": edge["target"], "name": nodes.get(edge["target"], {}).get("name",edge["target"]),
               "sourceNodeId": edge["source"], "sourceName": nodes.get(edge["source"],{}).get("name",edge["source"]),
               "relation": edge["relation"], **({"requirement":edge["requirement"]} if edge.get("requirement") else {})}
              for edge in edges]
    specification = item["specification"]
    fields={key:value for key,value in (specification or {}).get("fields",{}).items() if key in ("goal","non_goals","acceptance")}
    return {"specification": {**specification,"fields": {key:value[:2000] if isinstance(value,str) else value for key,value in fields.items()},
                              "fieldsTruncated":[key for key,value in fields.items() if isinstance(value,str) and len(value)>2000]} if specification else None,
            "inputs": inputs[:50], "inputsTruncated":len(inputs)>50,
            "sources": [record["canonicalRef"] for record in item["evidence"]]}


def compare(solutions):
    fields = ("purpose","element.kind","specification.goal","specification.acceptance","specification.non_goals","inputs")
    differences=[]
    for field in fields:
        values=[]
        for solution in solutions:
            if field=="purpose": value=solution["purpose"]
            elif field=="element.kind": value=(solution.get("element") or {}).get("kind")
            elif field=="inputs": value=solution["facts"]["inputs"]
            else: value=(solution["facts"].get("specification") or {}).get("fields",{}).get(field.split(".")[1])
            values.append({"solutionRef":solution["solutionRef"],"workspaceId":solution["snapshot"]["workspaceId"],"value":value})
        if len({json.dumps(item["value"],sort_keys=True,ensure_ascii=False) for item in values})>1:
            differences.append({"field":field,"values":values})
    sources=[{json.dumps(ref,sort_keys=True):ref for ref in solution["facts"]["sources"]} for solution in solutions]
    common=set.intersection(*(set(group) for group in sources)) if len(sources)>1 else set()
    return {"basis":"stored specifications and explicit graph inputs; no generated architectural conclusions",
            "commonSources":[sources[0][key] for key in sorted(common)],"differences":differences}
