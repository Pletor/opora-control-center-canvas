"""Pouze omezení běhu a předání původnímu CLI Graphify; žádný vlastní graf."""
import json
import runpy
import sys
from importlib.metadata import version
from pathlib import Path


def original_cli(arguments):
    sys.argv = ['graphify', *arguments]
    try:
        runpy.run_module('graphify', run_name='__main__')
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise


# Změřeno 2026-10-22: 875 souborů (agent-office) = 53 s a graph.json 14 MB. 1200 souborů se tak
# vejde do 120 s běhu (graphify_runtime) i 32 MiB výstupu s rezervou.
MAX_CODE_FILES = 1200
MAX_CODE_BYTES = 32 * 1024 * 1024


def corpus_error(count, size):
    """Proč korpus nelze poslat do Graphify, nebo None."""
    if not count or count > MAX_CODE_FILES:
        return f'Pro UI běh je potřeba 1–{MAX_CODE_FILES} zdrojových souborů; upravte .graphifyignore.'
    if size > MAX_CODE_BYTES:
        return 'Zdrojový kód překračuje 32 MiB.'
    return None


def ensure_html(output):
    """Doplní `graph.html`, který `cluster-only` nad 5000 uzlů vynechá.

    Původní CLI pak vytvoří souhrnný pohled po komunitách (`export html`, výchozí --node-limit 5000);
    menší grafy zůstávají beze změny.
    """
    produced = output / 'graphify-out'
    if not (produced / 'graph.html').is_file():
        original_cli(['export', 'html', '--graph', str(produced / 'graph.json'), '--node-limit', '5000'])


def main():
    from graphify.detect import detect


    root, output = map(Path, sys.argv[1:3])
    if version('graphifyy') != '0.9.24':
        raise SystemExit('Vyžadováno graphifyy==0.9.24.')
    corpus = detect(root, follow_symlinks=False, google_workspace=False)
    code = corpus.get('files', {}).get('code', [])
    print(json.dumps({'codeFiles': len(code), 'sensitiveSkipped': len(corpus.get('skipped_sensitive', []))}), flush=True)
    error = corpus_error(len(code), sum(Path(path).stat().st_size for path in code))
    if error:
        raise SystemExit(error)
    original_cli(['extract', str(root), '--code-only', '--max-workers', '2', '--out', str(output)])
    original_cli(['cluster-only', str(output), '--no-label'])
    ensure_html(output)


if __name__ == '__main__':
    main()
