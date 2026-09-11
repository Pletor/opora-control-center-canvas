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


def main():
    from graphify.detect import detect


    root, output = map(Path, sys.argv[1:3])
    if version('graphifyy') != '0.9.24':
        raise SystemExit('Vyžadováno graphifyy==0.9.24.')
    corpus = detect(root, follow_symlinks=False, google_workspace=False)
    code = corpus.get('files', {}).get('code', [])
    print(json.dumps({'codeFiles': len(code), 'sensitiveSkipped': len(corpus.get('skipped_sensitive', []))}), flush=True)
    if not code or len(code) > 500:
        raise SystemExit('Pro UI běh je potřeba 1–500 zdrojových souborů; upravte .graphifyignore.')
    if sum(Path(path).stat().st_size for path in code) > 32 * 1024 * 1024:
        raise SystemExit('Zdrojový kód překračuje 32 MiB.')
    original_cli(['extract', str(root), '--code-only', '--max-workers', '2', '--out', str(output)])
    original_cli(['cluster-only', str(output), '--no-label'])


if __name__ == '__main__':
    main()
