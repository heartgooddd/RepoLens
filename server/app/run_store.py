from datetime import datetime, timezone
from pathlib import Path
from .db import connect
from .run_models import Run


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def get_run(database: Path, run_id: str) -> Run | None:
    with connect(database) as db:
        row = db.execute('SELECT * FROM runs WHERE id = ?', (run_id,)).fetchone()
        if row is None:
            return None
        artifacts = [dict(item) for item in db.execute('SELECT * FROM artifacts WHERE run_id = ? ORDER BY path', (run_id,))]
        return Run(**dict(row), artifacts=artifacts)


def list_runs(database: Path, snapshot_id: str, limit: int = 20, offset: int = 0) -> dict:
    with connect(database) as db:
        ids = [row[0] for row in db.execute('SELECT id FROM runs WHERE snapshot_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?', (snapshot_id, limit, offset))]
        total = db.execute('SELECT count(*) FROM runs WHERE snapshot_id = ?', (snapshot_id,)).fetchone()[0]
    return {'items': [get_run(database, run_id) for run_id in ids], 'total': total, 'limit': limit, 'offset': offset}


def update_run(database: Path, run_id: str, **values) -> None:
    allowed = {'status', 'stage', 'started_at', 'ended_at', 'exit_code', 'error', 'model_usage'}
    if not values or not values.keys() <= allowed:
        raise ValueError('Invalid run fields')
    with connect(database) as db:
        db.execute(f"UPDATE runs SET {', '.join(key + ' = ?' for key in values)} WHERE id = ?", (*values.values(), run_id))
