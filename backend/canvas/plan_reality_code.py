"""Soubory a symboly z rozdílu commitu pro folii z kódu (`plan_reality`, F1), bez modelu.

`git show --unified=<celý soubor>` dá starý i nový obsah souboru a dotčené řádky; symbol (funkce, třída, komponenta,
route FastAPI, test) je změněný, když jeho rozsah dotčený řádek protíná. Python čte `ast`, TS/TSX a nepřeložitelný
Python regex `trace_git.SYMBOL`.
"""
import ast
import re

from backend.agi_pletor.linie import trace_git

HTTP = ("get", "post", "put", "patch", "delete")
TEST = re.compile(r"""^\s*(?:it|test)\(\s*['"`](.+?)['"`]""")
CODE = (".ts", ".tsx", ".js", ".jsx", ".mjs")


def _unquote(path):
    # Git uvozovkuje cesty s ne-ASCII znaky jako C řetězec s oktalovými bajty.
    if not path.startswith('"'):
        return path
    return path[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape").encode("latin-1").decode("utf-8")


def parse_diff(text):
    """Soubory z `git show --unified=<celý soubor>`: cesta, změna, starý a nový obsah, dotčené řádky nového."""
    found, item, body = [], None, False
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            item, body = {"path": _unquote(line.rsplit(" b/", 1)[-1]), "from": None, "change": "modified",
                          "old": [], "new": [], "touched": set()}, False
            found.append(item)
        elif item is None:
            continue
        elif body and (line[:1] in (" ", "+", "-", "\\") or not line):
            if line.startswith("+"):
                item["new"].append(line[1:])
                item["touched"].add(len(item["new"]))
            elif line.startswith("-"):
                item["old"].append(line[1:])
                item["touched"].add(len(item["new"]) + 1)  # smazaný řádek se počítá místu, kde byl
            elif not line.startswith("\\"):
                item["new"].append(line[1:])
                item["old"].append(line[1:])
        elif line.startswith("@@"):
            body = True
        elif line.startswith(("new file mode", "deleted file mode")):
            item["change"] = "added" if line.startswith("new") else "deleted"
        elif line.startswith("rename from "):
            item["change"], item["from"] = "renamed", _unquote(line[12:])
        elif line.startswith("rename to "):
            item["path"] = _unquote(line[10:])
    return found


def _py(body, touched, prefix=""):
    """`[(kind, name, line)]` nejvnitřnějších definic, které dotčené řádky protínají (třída jen bez metod)."""
    found = []
    for node in body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = min([node.lineno, *(item.lineno for item in node.decorator_list)])
        if touched is not None and not touched & set(range(start, node.end_lineno + 1)):
            continue
        inner = _py(node.body, touched, f"{prefix}{node.name}.") if isinstance(node, ast.ClassDef) else []
        kind, name = "test" if node.name.startswith("test_") else "symbol", prefix + node.name
        for item in node.decorator_list:  # @router.get("/cesta") → route „GET /cesta“
            if (isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr in HTTP
                    and item.args and isinstance(item.args[0], ast.Constant) and isinstance(item.args[0].value, str)):
                kind, name = "route", f"{item.func.attr.upper()} {item.args[0].value}"
        found += inner or [(kind, name, start)]
    return found


def _regex(lines, touched):
    """TS/TSX (a Python, který nejde přeložit): symbol platí od svého řádku po další symbol."""
    starts = [(index + 1, "symbol", match.group(1)) for index, line in enumerate(lines)
              if (match := trace_git.SYMBOL.match(line))]
    starts += [(index + 1, "test", match.group(1)) for index, line in enumerate(lines) if (match := TEST.match(line))]
    starts.sort()
    ends = [line - 1 for line, _, _ in starts[1:]] + [len(lines)]
    return [(kind, name, line) for (line, kind, name), end in zip(starts, ends)
            if touched is None or touched & set(range(line, end + 1))]


def symbols_of(path, lines, touched=None):
    """Symboly souboru podle přípony; `touched=None` = všechny."""
    if path.endswith(".py"):
        try:
            return _py(ast.parse("\n".join(lines)).body, touched)
        except (SyntaxError, ValueError):
            return _regex(lines, touched)
    return _regex(lines, touched) if path.endswith(CODE) else []


def changes(diffs):
    """`(soubory, symboly)` napříč commity `[(sha, rozdíl)]` od nejstaršího; pozdější změna přepíše dřívější."""
    files, symbols = {}, {}
    for sha, text in diffs:
        for item in parse_diff(text):
            path, change = item["path"], item["change"]
            if item["from"]:
                files.pop(item["from"], None)
                symbols = {(path if key[0] == item["from"] else key[0], *key[1:]): value | (
                    {"path": path} if key[0] == item["from"] else {}) for key, value in symbols.items()}
            before = files.get(path)
            change = "added" if before and before["change"] == "added" and change == "modified" else change
            files[path] = {"kind": "file", "name": path, "path": path, "line": None, "source": sha[:7],
                           "change": change} | ({"from": item["from"]} if item["from"] else {})
            symbols = {key: value for key, value in symbols.items() if key[0] != path or change != "deleted"}
            if change == "deleted":
                continue
            old = {name for _, name, _ in symbols_of(path, item["old"])}
            now = symbols_of(path, item["new"], item["touched"])
            for kind, name, line in now:
                first = (symbols.get((path, kind, name)) or {}).get("change") == "added" or name not in old
                symbols[(path, kind, name)] = {"kind": kind, "name": name, "path": path, "line": line,
                                               "source": sha[:7], "change": "added" if first else "modified"}
            kept = {name for _, name, _ in symbols_of(path, item["new"])}
            for kind, name, line in symbols_of(path, item["old"]):
                if name not in kept:
                    symbols[(path, kind, name)] = {"kind": kind, "name": name, "path": path, "line": line,
                                                   "source": sha[:7], "change": "deleted"}
    return list(files.values()), list(symbols.values())
