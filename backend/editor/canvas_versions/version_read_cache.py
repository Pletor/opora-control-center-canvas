"""Historie má vlastní čtecí spojení: velké staré snapshoty nedrží zámek plátna."""
import sqlite3
from contextlib import closing

from backend.canvas.read_cache import file_stamp, scope_stamp
from .version_content import current_token


def asset_stamp(canvas, project):
    root = canvas.folder(project).canvas / 'materials'
    return tuple(file_stamp(path) for path in sorted(root.rglob('*')) if path.is_file())


def list_cached(versions, project, workspace, summary, limit):
    # Jeden výpočet historie na instanci, ale nikdy pod společným zámkem služby.
    with versions._read_lock:
        for _ in range(3):
            try:
                result = _read_once(versions, project, workspace, summary, limit)
                if result is not None:
                    return result
            except sqlite3.OperationalError as error:
                if not any(word in str(error).lower() for word in ('locked', 'busy')):
                    raise
            except OSError:
                # Materiál může mezi otisky změnit externí editor; nepublikujeme cache.
                continue
        raise ValueError('Plátno nebo jeho soubory se během čtení změnily či jsou zamčené. Obnovte seznam verzí.')


def _read_once(versions, project, workspace, summary, limit):
    canvas = versions.canvas
    key = ('versions', project, workspace)
    with canvas.graph_lock, canvas.lock:
        canvas.view(project, workspace)  # validace rozsahu i před cache hitem
        stamp = scope_stamp(canvas, project, workspace)
        files = asset_stamp(canvas, project)
        token = (stamp, files)
        cached = versions._read_cache.get(key, token) if stamp is not None else None
        if cached is not None:
            return cached
        path = canvas.folder(project).database
    # SELECT * je nutný pro staré verze bez metadat; čteme jen pro cache miss.
    # Vlastní read-only spojení neporuší transakci sdíleného writeru.
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.25)) as reader:
        reader.row_factory = sqlite3.Row
        rows = reader.execute(
            'SELECT * FROM canvas_versions WHERE project_id=? AND workspace_id=? '
            'ORDER BY created_at DESC,rowid DESC LIMIT ?', (project, workspace, limit)).fetchall()
    summaries = [summary(row) for row in rows]
    del rows
    with canvas.graph_lock, canvas.lock:
        if stamp != scope_stamp(canvas, project, workspace) or files != asset_stamp(canvas, project):
            return None
        db = canvas.db_for(project)
        with db:
            db.execute('BEGIN')
            view, stored, snapshot = versions._capture(db, project, workspace)
            result = {'versions': summaries,
                      'dirty': False if view['readOnly'] else versions._dirty(db, project, workspace, view, stored, snapshot)}
            result['currentToken'] = current_token(view['graph'], stored, snapshot)
        # Kontrola také po načtení souborů: externí zápis nesmí publikovat starý token.
        if stamp != scope_stamp(canvas, project, workspace) or files != asset_stamp(canvas, project):
            return None
        if stamp is not None:
            versions._read_cache.put(key, token, result)
        return result
