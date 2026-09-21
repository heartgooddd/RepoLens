"""Single-owner local subprocess tasks with durable transitions and bounded output."""
import asyncio
import fcntl
import hashlib
import json
import os
import signal
import sys
from pathlib import Path
from uuid import uuid4

from .claims import verify_claims
from .config import Settings
from .db import connect
from .import_policy import fail, validate_path, MAX_FILE
from .pocketflow_adapter import COMMIT, isolated_environment, stub_command
from .run_models import ACTIVE, STAGES, RunRequest
from .run_store import get_run, now, update_run

MAX_LOG = 256 * 1024
MAX_ARTIFACT = 512 * 1024


class Runner:
    def __init__(self, settings: Settings, timeout: float = 180):
        self.settings = settings
        self.timeout = timeout
        self.tasks = {}
        self.processes = {}
        self.lock = None
        self.closing = False

    def start(self):
        self.lock = (self.settings.data_dir / 'runs' / '.runner.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError('Only one RepoLens backend may own this data directory') from None
        with connect(self.settings.database) as db:
            db.execute("UPDATE runs SET status='interrupted', ended_at=?, error=? WHERE status IN ('queued','running','cancelling')",
                       (now(), '后台已重启，遗留任务已中断；不会自动续跑。'))

    async def close(self):
        self.closing = True
        for run_id in list(self.tasks):
            run = get_run(self.settings.database, run_id)
            if run and run.status in ACTIVE:
                update_run(self.settings.database, run_id, status='interrupted', ended_at=now(), error='后台关闭，任务中断。')
            await self.terminate(run_id)
        if self.tasks:
            await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
        if self.lock:
            self.lock.close()

    def create(self, request: RunRequest):
        if self.closing:
            fail('runner_closing', '后台正在关闭，请稍后重试。', 503)
        with connect(self.settings.database) as db:
            if db.execute("SELECT id FROM runs WHERE status IN ('queued','running','cancelling') LIMIT 1").fetchone():
                fail('runner_busy', '当前已有任务，请完成或取消后再创建。', 409)
            snapshot = db.execute('SELECT id FROM snapshots WHERE id = ?', (str(request.snapshot_id),)).fetchone()
            scope = db.execute('SELECT path FROM folder_cards WHERE snapshot_id = ? AND path = ?', (str(request.snapshot_id), request.scope)).fetchone()
        if not snapshot:
            fail('snapshot_not_found', '项目快照不存在。', 404)
        if request.scope != '.':
            validate_path(request.scope)
        if not scope:
            fail('invalid_scope', '分析范围必须是此快照已登记的目录。')
        run_id = str(uuid4())
        directory = self.settings.data_dir / 'runs' / run_id
        directory.mkdir()
        (directory / 'run.log').write_text('替身任务已创建；不会发送模型请求。\n', encoding='utf-8')
        with connect(self.settings.database) as db:
            db.execute('''INSERT INTO runs(id,snapshot_id,mode,status,stage,language,topics,scope,scenario,created_at,upstream_commit)
                          VALUES (?,?,'stub','queued','queued',?,?,?,?,?,?)''',
                       (run_id, str(request.snapshot_id), request.language, request.topics, request.scope, request.scenario, now(), COMMIT))
        task = asyncio.create_task(self.execute(run_id))
        self.tasks[run_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(run_id, None))
        return get_run(self.settings.database, run_id)

    def prepare_input(self, run):
        destination = self.settings.data_dir / 'runs' / run.id / 'input'
        destination.mkdir()
        with connect(self.settings.database) as db:
            rows = list(db.execute('SELECT * FROM snapshot_files WHERE snapshot_id = ?', (run.snapshot_id,)))
        selected = [r for r in rows if run.scope == '.' or r['path'].startswith(run.scope + '/')]
        if not selected:
            raise ValueError('范围中没有已登记文件。')
        for row in selected:
            validate_path(row['path'])
            target = self.settings.data_dir / 'snapshots' / run.snapshot_id / row['path']
            if any(p.is_symlink() for p in [target, *target.parents]):
                raise ValueError('快照包含链接。')
            with target.open('rb') as stream:
                raw = stream.read(MAX_FILE + 1)
            if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('快照内容已变化。')
            relative = row['path'] if run.scope == '.' else row['path'][len(run.scope) + 1:]
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw)
        return destination

    async def terminate(self, run_id):
        process = self.processes.get(run_id)
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        await asyncio.sleep(0.2)
        # Escalate the group, including children that ignored SIGTERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()

    async def cancel(self, run_id):
        run = get_run(self.settings.database, run_id)
        if run is None:
            fail('run_not_found', '任务不存在。', 404)
        if run.status in ACTIVE:
            update_run(self.settings.database, run_id, status='cancelling')
            await self.terminate(run_id)
            current = get_run(self.settings.database, run_id)
            if current.status in ACTIVE:
                update_run(self.settings.database, run_id, status='cancelled', ended_at=now(), error='用户取消了任务。')
        return get_run(self.settings.database, run_id)

    async def execute(self, run_id):
        directory = self.settings.data_dir / 'runs' / run_id
        process = None
        try:
            run = get_run(self.settings.database, run_id)
            if run.status != 'queued':
                return
            update_run(self.settings.database, run_id, status='running', started_at=now(), stage='preparing')
            input_dir = await asyncio.to_thread(self.prepare_input, run)
            if get_run(self.settings.database, run_id).status != 'running':
                return
            command = stub_command(input_dir, directory / 'output', run.language, run.topics, run.scenario)
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-B', '-u', str(Path(__file__).with_name('run_supervisor.py')), str(os.getpid()), json.dumps(command),
                cwd=directory, env=isolated_environment(directory), stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True,
            )
            self.processes[run_id] = process
            if get_run(self.settings.database, run_id).status != 'running':
                await self.terminate(run_id)
                return
            async with asyncio.timeout(self.timeout):
                with (directory / 'run.log').open('ab') as log:
                    size = log.tell()
                    pending = b''
                    while chunk := await process.stdout.read(4096):
                        size += len(chunk)
                        if size > MAX_LOG:
                            raise ValueError('日志超过上限。')
                        log.write(chunk); log.flush()
                        pending += chunk
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            marker = line.decode('utf-8', errors='replace')
                            if marker.startswith('REPOLENS_STAGE:') and marker.split(':', 1)[1] in STAGES:
                                update_run(self.settings.database, run_id, stage=marker.split(':', 1)[1])
                    code = await process.wait()
            current = get_run(self.settings.database, run_id)
            if current.status != 'running':
                return
            if code != 0:
                update_run(self.settings.database, run_id, status='failed', exit_code=code, ended_at=now(), error=f'替身进程退出码 {code}，未登记成功产物。')
                return
            artifacts = self.collect_artifacts(run, directory)
            # No await between status check and terminal commit: cancellation cannot overwrite success or vice versa.
            with connect(self.settings.database) as db:
                db.execute('BEGIN IMMEDIATE')
                try:
                    for artifact in artifacts:
                        db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)', artifact)
                    db.execute("UPDATE runs SET status='succeeded',stage='complete',ended_at=?,exit_code=0 WHERE id=? AND status='running'", (now(), run_id))
                    db.commit()
                except BaseException:
                    db.rollback(); raise
        except Exception:
            await self.terminate(run_id)
            current = get_run(self.settings.database, run_id)
            if current and current.status == 'running':
                update_run(self.settings.database, run_id, status='failed', ended_at=now(), exit_code=process.returncode if process else None,
                           error='任务失败：超时、快照校验或产物检查未通过。请检查日志并重新导入／重试。')
        finally:
            self.processes.pop(run_id, None)

    def collect_artifacts(self, run, directory):
        root = directory / 'output'
        if not (root / 'project' / 'index.md').is_file():
            raise ValueError('Missing index.md')
        claims = root / 'project' / 'folder-claims.json'
        if claims.is_file() and not claims.is_symlink() and claims.stat().st_size <= MAX_ARTIFACT:
            result = verify_claims(self.settings, run.snapshot_id, json.loads(claims.read_text()))
            (root / 'project' / 'verified-claims.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        entries = []
        total = 0
        for file in sorted(root.rglob('*')):
            if file.is_symlink():
                raise ValueError('Artifact link')
            if not file.is_file():
                continue
            if file.suffix not in ('.md', '.json'):
                continue
            size = file.stat().st_size
            total += size
            if size > MAX_ARTIFACT or total > 4 * 1024 * 1024 or len(entries) >= 32:
                raise ValueError('Artifact limit')
            raw = file.read_bytes()
            raw.decode('utf-8')
            entries.append((str(uuid4()), run.id, file.relative_to(root).as_posix(), size, hashlib.sha256(raw).hexdigest()))
        return entries
