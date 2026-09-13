"""Skutečný Windows junction důkaz bez oprávnění vytvářet symlinky."""
import os
import subprocess

import pytest

from backend.agents.runs.task_handoff_tools import DocumentTools


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction boundary')
def test_junction_rebinding_never_writes_to_outside_directory(tmp_path):
    root, outside = tmp_path / 'workspace', tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    tools = DocumentTools(root, {'map': {}, 'documents': {}})
    root.rename(tmp_path / 'original')
    linked = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(root), str(outside)], capture_output=True, text=True, timeout=10, check=False)
    assert linked.returncode == 0, linked.stderr
    try:
        with pytest.raises(ValueError):
            tools.write_result('# Zápis musí být odmítnut')
        assert not (outside / 'result.md').exists()
    finally:
        # rmdir odstraňuje pouze junction, nikoli cílový adresář a jeho obsah.
        os.rmdir(root)
