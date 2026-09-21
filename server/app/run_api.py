import hashlib
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import Response

from .config import Settings
from .db import connect
from .import_policy import fail, validate_path
from .run_models import ACTIVE, LogSlice, Run, RunRequest
from .run_store import get_run, list_runs
from .runner import Runner, MAX_ARTIFACT


def routes(settings: Settings, runner: Runner) -> APIRouter:
    api = APIRouter()

    def require_run(run_id):
        run = get_run(settings.database, str(run_id))
        if run is None:
            fail('run_not_found', '任务不存在。', 404)
        return run

    @api.get('/api/runner')
    def configuration():
        return runner.configuration()

    @api.post('/api/runs', response_model=Run, status_code=201)
    async def create(body: RunRequest):
        return runner.create(body)

    @api.get('/api/runs')
    def history(snapshot_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return list_runs(settings.database, str(snapshot_id), limit, offset)

    @api.get('/api/runs/{run_id}', response_model=Run)
    def detail(run_id: UUID):
        return require_run(run_id)

    @api.post('/api/runs/{run_id}/cancel', response_model=Run)
    async def cancel(run_id: UUID):
        return await runner.cancel(str(run_id))

    @api.get('/api/runs/{run_id}/logs', response_model=LogSlice)
    def logs(run_id: UUID, offset: int = Query(0, ge=0)):
        run = require_run(run_id)
        path = settings.data_dir / 'runs' / run.id / 'run.log'
        if path.is_symlink():
            fail('log_changed', '日志路径已变化。', 409)
        try:
            with path.open('rb') as stream:
                stream.seek(offset)
                raw = stream.read(32768)
                # Avoid splitting a valid UTF-8 sequence at the chunk boundary.
                while raw:
                    try:
                        content = raw.decode('utf-8')
                        break
                    except UnicodeDecodeError as error:
                        if error.reason == 'unexpected end of data':
                            extra = stream.read(1)
                            if extra:
                                raw += extra
                                continue
                        content = raw.decode('utf-8', errors='replace')
                        break
                else:
                    content = ''
        except OSError:
            fail('log_missing', '日志文件已丢失。', 409)
        return LogSlice(offset=offset, next_offset=offset+len(raw), content=content, finished=run.status not in ACTIVE)

    @api.get('/api/runs/{run_id}/artifacts/{artifact_id}')
    def artifact(run_id: UUID, artifact_id: UUID, download: bool = False):
        run = require_run(run_id)
        if run.status != 'succeeded':
            fail('result_unavailable', '任务未成功，不提供成功产物。', 409)
        with connect(settings.database) as db:
            row = db.execute('SELECT * FROM artifacts WHERE run_id = ? AND id = ?', (str(run_id), str(artifact_id))).fetchone()
        if row is None:
            fail('artifact_not_found', '产物不存在。', 404)
        validate_path(row['path'])
        base = settings.data_dir / 'runs' / str(run_id) / 'output'
        path = base / row['path']
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.resolve().is_relative_to(base.resolve()):
            fail('artifact_changed', '产物路径已变化。', 409)
        try:
            with path.open('rb') as stream:
                raw = stream.read(MAX_ARTIFACT+1)
        except OSError:
            fail('artifact_missing', '产物已丢失。', 409)
        if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            fail('artifact_changed', '产物校验失败，请重新运行。', 409)
        if download:
            return Response(raw, media_type='application/octet-stream', headers={
                'Content-Disposition': 'attachment; filename="repolens-artifact' + path.suffix + '"',
                'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'; sandbox"})
        return {'path': row['path'], 'content': raw.decode('utf-8'), 'sha256': row['sha256'], 'mode': run.mode}

    return api
