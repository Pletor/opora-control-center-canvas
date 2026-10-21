"""Budget authority survives restart and every new history table refuses old-backup restore."""
import sqlite3

import pytest

from backend.canvas.opora_execution_budget_restore import refuse_budget_restore
from database.schema.opora_execution_budget_schema import BUDGET_SCHEMA, BUDGET_TABLES
from database.schema.project_schema import PROJECT_TABLES


@pytest.mark.parametrize('table',BUDGET_TABLES)
def test_every_budget_authority_table_blocks_old_backup_restore(table):
    with sqlite3.connect(':memory:') as db:
        db.executescript(BUDGET_SCHEMA)
        refuse_budget_restore(db)
        columns=list(db.execute(f'PRAGMA table_info({table})'))
        names=[row[1] for row in columns]
        values=[1 if name=='id' and table.endswith('_clock') else 0 if name=='frozen' else '1' for name in names]
        db.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",values)
        db.commit()
        before=list(db.iterdump())
        with pytest.raises(ValueError,match='execution budget'):
            refuse_budget_restore(db)
        assert list(db.iterdump())==before
        assert PROJECT_TABLES[table]=='project_id'
