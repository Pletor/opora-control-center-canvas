"""Přehled komunit Graphify pro lehkou mapu: čistá funkce nad načteným grafem, bez I/O."""
from collections import Counter, defaultdict
import math

MAX_COMMUNITIES = 300
MAX_EDGES = 2000
TOP_NODES = 5
TOP_PATHS = 3


def _path(node):
    value = node.get('source_file')
    if not isinstance(value, str) or not value.strip():
        return None
    parts = [part for part in value.replace('\\', '/').split('/') if part not in ('', '.')]
    return '/'.join(parts) or None


def _folders(path):
    return path.split('/')[:-1]


def _common_prefix(paths):
    if len(set(paths)) == 1:
        return paths[0]
    prefix = []
    for parts in zip(*(_folders(path) for path in paths)):
        if any(part != parts[0] for part in parts):
            break
        prefix.append(parts[0])
    return '/'.join(prefix)


def community_name(paths):
    """Jméno z nejdelšího společného prefixu složek; jinak nejčastější první složka + „a další“."""
    if not paths:
        return 'smíšené'
    prefix = _common_prefix(paths)
    if prefix:
        return prefix
    first = Counter(_folders(path)[0] for path in paths if _folders(path))
    if first:
        return first.most_common(1)[0][0] + ' a další'
    return 'smíšené'


def _weight(link):
    try:
        value = float(link.get('weight', 1))
    except (TypeError, ValueError):
        return 1.0
    return value if math.isfinite(value) else 1.0


def _disambiguate(communities):
    """Stejné jméno u více komunit zpřesní nejčastější podsložkou, pak nejpropojenějším uzlem, nakonec pořadím."""
    def deeper_folder(item):
        base = item['name'].removesuffix(' a další')
        folder = item['paths'][0] if item['paths'] else ''
        if not folder.startswith(base + '/'):
            return None
        return folder + (' a další' if item['name'].endswith(' a další') else '')

    def with_node(item):
        return item['name'] + ' · ' + item['top'][0]['label'].rsplit('/', 1)[-1] if item['top'] else None

    for rename in (deeper_folder, with_node):
        repeated = Counter(item['name'] for item in communities)
        for item in communities:
            better = rename(item) if repeated[item['name']] > 1 else None
            if better:
                item['name'] = better
    seen = Counter()
    repeated = Counter(item['name'] for item in communities)
    for item in communities:
        if repeated[item['name']] > 1:
            seen[item['name']] += 1
            if seen[item['name']] > 1:
                item['name'] = '%s (%d)' % (item['name'], seen[item['name']])


def overview(graph):
    nodes = graph.get('nodes') or []
    links = graph.get('links', graph.get('edges')) or []
    community_of, members = {}, defaultdict(list)
    for node in nodes:
        if not isinstance(node, dict) or 'id' not in node or node.get('community') is None:
            continue
        community_of[node['id']] = node['community']
        members[node['community']].append(node)
    degree = Counter()
    pairs = defaultdict(lambda: [0.0, 0])
    for link in links:
        if not isinstance(link, dict):
            continue
        source, target = link.get('source'), link.get('target')
        degree[source] += 1
        degree[target] += 1
        a, b = community_of.get(source), community_of.get(target)
        if a is None or b is None or a == b:
            continue
        key = tuple(sorted((a, b), key=str))
        pairs[key][0] += _weight(link)
        pairs[key][1] += 1

    communities = []
    for cid, group in members.items():
        paths = [path for path in map(_path, group) if path]
        folders = Counter('/'.join(_folders(path)[:2]) for path in paths if _folders(path))
        ranked = sorted(group, key=lambda node: (-degree[node['id']], str(node['id'])))[:TOP_NODES]
        communities.append({
            'id': cid, 'name': community_name(paths), 'rawName': group[0].get('community_name'),
            'size': len(group), 'files': len(set(paths)),
            'kinds': dict(Counter(str(node.get('file_type') or 'neznámé') for node in group)),
            'top': [{'id': node['id'], 'label': node.get('label') or str(node['id']),
                     'source_file': _path(node), 'degree': degree[node['id']]} for node in ranked],
            'paths': [path for path, _ in sorted(folders.items(), key=lambda item: (-item[1], item[0]))[:TOP_PATHS]],
        })
    communities.sort(key=lambda item: (-item['size'], str(item['id'])))
    _disambiguate(communities)
    truncated = len(communities) > MAX_COMMUNITIES
    communities = communities[:MAX_COMMUNITIES]
    kept = {item['id'] for item in communities}
    edges = [{'source': a, 'target': b, 'weight': round(weight, 6), 'count': count}
             for (a, b), (weight, count) in pairs.items() if a in kept and b in kept]
    edges.sort(key=lambda item: (-item['weight'], -item['count'], str(item['source']), str(item['target'])))
    if len(edges) > MAX_EDGES:
        truncated = True
        edges = edges[:MAX_EDGES]
    return {
        'counts': {'nodes': len(nodes), 'edges': len(links), 'communities': len(members)},
        'communities': communities, 'edges': edges, 'truncated': truncated,
    }
