"""Read-only verification of the single M3 real acceptance run; never creates a task."""
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = '1acf3d68-c857-4acf-89d9-bee17f98c512'
API = 'http://127.0.0.1:8000/api'


def get(path):
    with urllib.request.urlopen(API + path, timeout=15) as response:
        return json.load(response)


def main():
    run = get('/runs/' + RUN_ID)
    assert run['status'] == 'succeeded' and run['mode'] == 'pocketflow'
    assert (run['scope'], run['language'], run['topics']) == ('utils', 'zh', 3)
    db = sqlite3.connect(f'file:{ROOT / "var/repolens.sqlite3"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    row = dict(db.execute('SELECT * FROM runs WHERE id=?', (RUN_ID,)).fetchone())
    assert all(run[key] == value for key, value in row.items())
    artifacts = [dict(r) for r in db.execute('SELECT * FROM artifacts WHERE run_id=? ORDER BY path', (RUN_ID,))]
    assert artifacts == sorted(run['artifacts'], key=lambda a: a['path'])
    directory = ROOT / 'var/runs' / RUN_ID
    for artifact in artifacts:
        raw = (directory / 'output' / artifact['path']).read_bytes()
        returned = get(f'/runs/{RUN_ID}/artifacts/{artifact["id"]}')
        assert len(raw) == artifact['size_bytes']
        assert hashlib.sha256(raw).hexdigest() == artifact['sha256'] == returned['sha256']
        assert raw.decode() == returned['content']
    files = list(db.execute("SELECT * FROM snapshot_files WHERE snapshot_id=? AND path LIKE 'utils/%' ORDER BY path", (run['snapshot_id'],)))
    assert len(files) == 4
    for source in files:
        copied = directory / 'input' / source['path'].removeprefix('utils/')
        original = ROOT / 'var/snapshots' / run['snapshot_id'] / source['path']
        assert copied.read_bytes() == original.read_bytes()
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == source['sha256']
    usage = json.loads(run['model_usage'])
    assert usage == json.loads((directory/'model-data/usage.json').read_text())
    assert usage == json.loads((directory/'output/project/model-usage.json').read_text())
    assert usage['call_count'] == 7 and usage['retry_performed'] is False
    assert all(c['returned_model'] == run['model_name'] and c['finish_reason'] == 'stop' for c in usage['calls'])
    claims = json.loads((directory/'output/project/verified-claims.json').read_text())
    report = {'run_id': RUN_ID, 'snapshot_id': run['snapshot_id'], 'status': run['status'],
              'mode': run['mode'], 'scope': run['scope'], 'language': run['language'], 'topics': run['topics'],
              'created_at': run['created_at'], 'started_at': run['started_at'], 'ended_at': run['ended_at'],
              'model': run['model_name'], 'upstream_commit': run['upstream_commit'], 'prompt_version': run['prompt_version'],
              'input_files_verified': len(files), 'artifacts_verified': artifacts,
              'database_api_files_equal': True, 'usage_equal': True, 'model_usage': usage,
              'claim_types': [c['claim_type'] for c in claims],
              'real_run_count': db.execute("SELECT COUNT(*) FROM runs WHERE mode='pocketflow'").fetchone()[0]}
    db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
