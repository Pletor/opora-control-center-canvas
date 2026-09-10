"""Odkazy [[uzel]] a zpětné odkazy nad stejnou identitou uzlů; žádný druhý graf.

Cílem odkazu smí být jen existující uzel aktuálního pracovního prostoru. Nenalezené
jméno se hlásí jako nevyřešené, uzel se z něj nevytváří. Počty jsou skutečné, ne odhad.
"""
import re

from .graph import valid_id

LINK = re.compile(r"\[\[([^\[\]\n]{1,160})\]\]")


def link_names(text):
    """Jména z [[...]] v pořadí prvního výskytu, bez duplicit."""
    found = []
    for match in LINK.finditer(text or ""):
        name = match.group(1).strip()
        if name and name not in found:
            found.append(name)
    return found


class NodeLinks:
    def __init__(self, canvas):
        self.canvas = canvas

    def _layer(self, project, workspace):
        view = self.canvas.view(project, workspace)
        if view["readOnly"]:
            raise ValueError("Main je pouze pro čtení; odkazy se editují v pracovním prostoru.")
        return view["graph"]

    def targets(self, project, workspace):
        """Nabídka pro [[: skutečné uzly této pracovní revize."""
        graph = self._layer(project, workspace)
        return {
            "targets": [
                {"id": n["id"], "name": n["name"], "kind": n["kind"], "parentId": n["parentId"]}
                for n in graph["nodes"]
            ]
        }

    def resolve(self, name, nodes):
        """Odkaz se váže na ID uzlu; jméno je jen pohodlný zápis."""
        key = name.strip().casefold()
        for node in nodes:
            if node["id"] == name.strip():
                return node
        for node in nodes:
            if node["name"].strip().casefold() == key:
                return node
        return None

    def links(self, project, workspace, node):
        graph = self._layer(project, workspace)
        nodes = graph["nodes"]
        by_id = {n["id"]: n for n in nodes}
        if not valid_id(node) or node not in by_id:
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        texts = self.canvas.texts.read_all(project, workspace)

        def entry(target, via, direction):
            return {
                "nodeId": target["id"],
                "name": target["name"],
                "kind": target["kind"],
                "via": via,
                "direction": direction,
            }

        outgoing, unresolved = [], []
        for name in link_names(texts.get(node, "")):
            target = self.resolve(name, nodes)
            if target is None:
                unresolved.append(name)
            elif target["id"] != node and all(o["nodeId"] != target["id"] for o in outgoing):
                outgoing.append(entry(target, "text", "out"))

        backlinks = []
        for source in nodes:
            if source["id"] == node:
                continue
            for name in link_names(texts.get(source["id"], "")):
                target = self.resolve(name, nodes)
                if target is not None and target["id"] == node:
                    backlinks.append(entry(source, "text", "in"))
                    break

        edges = []
        for edge in graph["edges"]:
            other, direction = (edge["target"], "out") if edge["source"] == node else (edge["source"], "in") if edge["target"] == node else (None, None)
            if other in by_id and other != node:
                edges.append({**entry(by_id[other], "edge", direction), "edgeId": edge["id"]})

        return {
            "node": node,
            "outgoing": outgoing,
            "unresolved": unresolved,
            "backlinks": backlinks,
            "edges": edges,
            "counts": {
                "outgoing": len(outgoing),
                "backlinks": len(backlinks),
                "edges": len(edges),
                "unresolved": len(unresolved),
            },
        }
