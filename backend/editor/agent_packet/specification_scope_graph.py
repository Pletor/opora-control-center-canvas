"""Bounded graph indexes for the pure specification selector (no coverage claim)."""

MAX_NODES = 2000
MAX_EDGES = 8000


class ScopeGraph:
    def __init__(self, graph):
        self.nodes, self.edges = graph["nodes"], graph["edges"]
        if len(self.nodes) > MAX_NODES or len(self.edges) > MAX_EDGES:
            raise ValueError("Specification scope exceeds graph bounds")
        self.by_id = self._unique(self.nodes)
        self._unique(self.edges)
        self.children = {}
        for node in self.nodes:
            self.children.setdefault(node.get("parentId"), []).append(node["id"])
        # Validate cycles even outside the selected branch; never silently close one.
        finished = set()
        for identifier in self.by_id:
            path, cursor = set(), identifier
            while cursor in self.by_id and cursor not in finished:
                if cursor in path:
                    raise ValueError("Cyclic specification ancestry")
                path.add(cursor)
                cursor = self.by_id[cursor].get("parentId")
            finished.update(path)

    @staticmethod
    def _unique(items):
        result = {}
        for item in items:
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in result:
                raise ValueError("Missing or duplicate graph identity")
            result[identifier] = item
        return result

    def require(self, identifier):
        if identifier not in self.by_id:
            raise ValueError("Missing required specification node")
        return self.by_id[identifier]

    def lineage(self, identifier):
        result = []
        while identifier:
            node = self.require(identifier)
            result.append(identifier)
            identifier = node.get("parentId")
        return result

    def descendants(self, identifier):
        self.require(identifier)
        result, pending = set(), [identifier]
        while pending:
            current = pending.pop()
            result.add(current)
            pending.extend(self.children.get(current, ()))
        return result
