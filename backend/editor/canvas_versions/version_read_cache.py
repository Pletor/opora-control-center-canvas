"""Živé čtení historie: velké staré snapshoty nedrží zámek plátna.

Cache živého výsledku je vypnutá: externí soubory nemají spolehlivou revizi.
Cachují se pouze souhrny uložených verzí, závislé výhradně na SQLite.
Není potřeba žádný rglob, _capture jednou načte jen odkazované materiály.
"""
import sqlite3
from contextlib import closing

from backend.canvas.read_cache import database_stamp, file_stamp
from .version_content import current_token


def list_cached(versions, project, workspace, summary, limit):
    # Dirty/currentToken se vždy počítají z čerstvého obsahu.
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
                continue
        raise ValueError('Plátno nebo jeho soubory se během čtení změnily či jsou zamčené. Obnovte seznam verzí.')


def _read_once(versions, project, workspace, summary, limit):
    canvas = versions.canvas
    canvas.view(project, workspace)
    with canvas.graph_lock, canvas.lock:
        db = canvas.db_for(project)
        stamp = (database_stamp(canvas.db), database_stamp(db))
        path = canvas.folder(project).database
        key = ('summaries', project, workspace, limit)
        cacheable = not db.in_transaction and not canvas.db.in_transaction
        cached = versions._read_cache.get_snapshot(key, stamp) if cacheable else None
    summaries = versions._read_cache.decode(cached)
    if summaries is None:
        # Samostatné read-only spojení neporuší transakci sdíleného writeru.
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.25)) as reader:
            reader.row_factory = sqlite3.Row
            rows = reader.execute(
                'SELECT * FROM canvas_versions WHERE project_id=? AND workspace_id=? '
                'ORDER BY created_at DESC,rowid DESC LIMIT ?', (project, workspace, limit)).fetchall()
        summaries = [summary(row) for row in rows]
        del rows
    asset_stamps = {}
    with canvas.graph_lock, canvas.lock:
        if stamp != (database_stamp(canvas.db), database_stamp(db)):
            return None
        if db.in_transaction:
            view, stored, snapshot = versions._capture(db, project, workspace, asset_stamps=asset_stamps)
            result = {'versions': summaries,
                      'dirty': False if view['readOnly'] else versions._dirty(db, project, workspace, view, stored, snapshot)}
            result['currentToken'] = current_token(view['graph'], stored, snapshot)
        else:
            with db:
                db.execute('BEGIN')
                view, stored, snapshot = versions._capture(db, project, workspace, asset_stamps=asset_stamps)
                result = {'versions': summaries,
                          'dirty': False if view['readOnly'] else versions._dirty(db, project, workspace, view, stored, snapshot)}
                result['currentToken'] = current_token(view['graph'], stored, snapshot)
    if any(file_stamp(path) != saved for path, saved in asset_stamps.items()):
        return None
    with canvas.graph_lock, canvas.lock:
        if stamp != (database_stamp(canvas.db), database_stamp(db)):
            return None
        publish = cacheable and not db.in_transaction and not canvas.db.in_transaction
    if publish and cached is None:
        # Pozdní publikace nese staré razítko, další writer tedy vynutí miss.
        versions._read_cache.put(key, stamp, summaries)
    return result
