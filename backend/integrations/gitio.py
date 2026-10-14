import os
import re
import subprocess
from pathlib import Path


def github_url(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_-][A-Za-z0-9._-]*", value
    ):
        raise ValueError(
            "Zadejte přesnou HTTPS adresu GitHub vlastníka a repozitáře, bez tokenu a parametrů."
        )
    return value


def git(root, *args, timeout=15, optional=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    # Hooky a fsmonitor nesmí při pozorování spouštět projektový kód. Dlouhé cesty: worktree
    # v datové složce + hluboké soubory repozitáře přesahují na Windows limit 260 znaků.
    command = [
        "git",
        "-c",
        "core.hooksPath=" + str(Path(__file__).resolve().parent / "disabled-hooks"),
        "-c",
        "core.fsmonitor=false",
        "-c",
        "submodule.recurse=false",
        "-c",
        "core.longpaths=true",
    ]
    if root is not None:
        command += ["-C", str(root)]
    command += list(args)
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=env,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        if optional:
            return None
        raise ValueError(
            "Git operace selhala. Ověřte přístup, čistotu pracovního stromu a dostupnost zdroje."
        )
    return result.stdout.decode("utf-8", errors="replace").strip()
