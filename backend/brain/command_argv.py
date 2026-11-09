"""Read command text as data: bounded shell tokens or literal Python subprocess argv."""
import ast
import re
import shlex


def _script(argv):
    executable = argv[0].replace("\\", "/").split("/")[-1] if argv else ""
    if not argv or not (argv[0] == "sys.executable" or re.fullmatch(r"(?:python(?:\d+(?:\.\d+)*)?|py)(?:\.exe)?", executable)):
        raise ValueError("A Python invocation is required.")
    args = argv[1:]
    while args and args[0] in ("-I", "-u", "-B", "-3"):
        args = args[1:]
    if not args or args[0].replace("\\", "/").split("/")[-1] != "opora_read.py":
        raise ValueError("Use the existing read client.")
    if any(token in (";", "&&", "||", "|", ">", "<") for token in args):
        raise ValueError("Command composition is not allowed.")
    return args[1:]


def _python(text):
    tree = ast.parse(text)
    result, literals = [], {}
    for statement in tree.body:
        if isinstance(statement, ast.Import) and all(item.name in ("sys", "subprocess") and not item.asname for item in statement.names):
            continue
        if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id not in ("sys", "subprocess")
                and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str)):
            literals[statement.targets[0].id] = statement.value.value
            continue
        if not isinstance(statement, ast.Expr):
            raise ValueError("Only literal subprocess invocations are supported.")
        call = statement.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and (call.func.value.id, call.func.attr) == ("sys", "exit"):
            if len(call.args) != 1 or call.keywords:
                raise ValueError("Invalid exit wrapper.")
            call = call.args[0]
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "subprocess"
                and call.func.attr in ("run", "call", "check_call", "check_output")
                and len(call.args) == 1 and isinstance(call.args[0], (ast.List, ast.Tuple))):
            raise ValueError("A literal subprocess argv is required.")
        for keyword in call.keywords:
            if keyword.arg not in ("check", "capture_output", "text", "encoding", "timeout") or not isinstance(keyword.value, ast.Constant):
                raise ValueError("Subprocess context overrides are not accepted.")
        argv = []
        for item in call.args[0].elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                argv.append(item.value)
            elif isinstance(item, ast.Name) and item.id in literals:
                argv.append(literals[item.id])
            elif isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and (item.value.id, item.attr) == ("sys", "executable"):
                argv.append("sys.executable")
            else:
                raise ValueError("Computed arguments are not executed or accepted.")
        result.append(_script(argv))
    if not result:
        raise ValueError("No command found.")
    return result


def commands(text):
    if not isinstance(text, str) or len(text) > 64000:
        raise ValueError("Command response is missing or too large.")
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
    if not blocks:
        blocks = [text]
    result = []
    for block in blocks:
        if "subprocess." in block or "import sys" in block:
            result.extend(_python(block))
        else:
            for line in block.replace("\\\n", " ").splitlines():
                if line.strip():
                    result.append(_script(shlex.split(line)))
    return result
