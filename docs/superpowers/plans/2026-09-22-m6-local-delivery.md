# M6 Local Delivery Implementation Plan

> Execute inline using executing-plans and TDD. User approved the design and technical G2/G3 delivery. No additional paid model calls or real-user claims.

**Goal:** Reproduce a local installation from Git, launch it by double-click, and safely back up and restore its persisted work.

**Architecture:** Product-owned delivery modules handle installation and process ownership. A global data lease excludes backend writes during SQLite plus file backup. FastAPI optionally serves the built frontend at the existing loopback API port. Backup restore publishes only validated fresh directories.

**Tech Stack:** Python standard library, FastAPI, SQLite backup API, zsh .command wrappers, npm lockfile build, pytest and Playwright.

## Task 1: Data maintenance and static delivery

- [ ] Add failing `server/tests/test_delivery.py` tests for a second data lease, backup while server owns data, static frontend serving and unknown API routes.
- [ ] Implement `server/app/data_lease.py` with `fcntl.flock(LOCK_EX | LOCK_NB)` and release in lifespan; integrate in `server/app/main.py` before migration and worker startup.
- [ ] Serve `web/dist` only when `REPOLENS_SERVE_WEB=1`, after API routes. Use `/` index and static assets without a catch-all that converts API 404 into HTML.
- [ ] Run `server/.venv/bin/python -m pytest -q server/tests/test_delivery.py`; expect pass after the initial failures.

## Task 2: Backup and restore

- [ ] Add tests creating a real uploaded project and completed stub run, backing up and opening restored project/source/artifacts. Assert refusal for live service, changed file, symlink, traversal manifest and nonempty/existing destination.
- [ ] Implement `server/app/backup.py`: source lease, `sqlite3.Connection.backup`, regular files only, versioned SHA-256 manifest, DB reference validation, fresh staging and atomic rename. CLI `python -m app.backup create DEST` / `restore BACKUP DEST`.
- [ ] Run delivery and run regression tests and inspect backup contents for exclusion of keys/tests; commit scoped verified module changes under G2.

## Task 3: Installation and lifecycle

- [ ] Add failing `server/tests/test_local_tools.py` tests for dependency preflight, pinned source preparation (local Git fixture only for mechanics), wrong/dirty checkout refusal, port conflict and process-owner matching.
- [ ] Create `scripts/install.py`, `scripts/local.py`, and `.command` wrappers. Use checked argv subprocesses with timeouts, fixed HTTPS URL/Commit, two venvs with lockfiles, `npm ci` and build. No upstream setup scripts or auto model calls.
- [ ] Launch the backend with built frontend on 127.0.0.1:8000; a foreground supervisor owns a control socket, children and cleanup. Stop via private local control socket, not stale PID alone. Keep readable runtime logs under var/local-delivery, honor absolute REPOLENS_DATA_DIR.
- [ ] Run `server/.venv/bin/python -m pytest -q server/tests/test_local_tools.py server/tests/test_delivery.py` and `npm run build` in web.

## Task 4: Reproduction, UI and documentation

- [ ] Commit G2 implementation, clone the local repository into a new ignored acceptance directory with spaces and install from scratch using official network sources; verify no dependency/upstream reuse by path.
- [ ] Start/stop using .command entry, verify browser project import and stub run; back up actual saved data while stopped and restore to new directory, open M3 historical result/source in browser without model call.
- [ ] Write `docs/05-local-setup-and-trial.md`, `evidence/m6/acceptance.md`, `evidence/m6/trial-observation-template.md`; update README/guide/roadmap with separate technical and user-trial statuses.
- [ ] Run full backend tests, frontend build and browser critical flows; apply verification-before-completion, independent spec/standards code review and focused fixes.
- [ ] G2 commit scoped evidence/docs, G3 ff-only merge to main, retain phase branch, no push; record post-merge smoke and 0/3 real users.
