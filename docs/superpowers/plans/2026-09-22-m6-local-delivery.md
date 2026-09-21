# M6 Local Delivery Implementation Plan

> Execute inline using executing-plans and TDD. User approved the design and technical G2/G3 delivery. No additional paid model calls or real-user claims.

**Goal:** Reproduce a local installation from Git, launch it by double-click, and safely back up and restore its persisted work.

**Architecture:** Product-owned delivery modules handle installation and process ownership. A global data lease excludes backend writes during SQLite plus file backup. FastAPI optionally serves the built frontend at the existing loopback API port. Backup restore publishes only validated fresh directories.

**Tech Stack:** Python standard library, FastAPI, SQLite backup API, zsh .command wrappers, npm lockfile build, pytest and Playwright.

## Task 1: Data maintenance and static delivery

- [x] Add failing `server/tests/test_delivery.py` tests for a second data lease, backup while server owns data, static frontend serving and unknown API routes.
- [x] Implement `server/app/data_lease.py` with `fcntl.flock(LOCK_EX | LOCK_NB)` and release in lifespan; integrate in `server/app/main.py` before migration and worker startup.
- [x] Serve `web/dist` only when `REPOLENS_SERVE_WEB=1`, after API routes. Use `/` index and static assets without a catch-all that converts API 404 into HTML.
- [x] Run `server/.venv/bin/python -m pytest -q server/tests/test_delivery.py`; expect pass after the initial failures.

## Task 2: Backup and restore

- [x] Add tests creating a real uploaded project and completed stub run, backing up and opening restored project/source/artifacts. Assert refusal for live service, changed file, symlink, traversal manifest and nonempty/existing destination.
- [x] Implement `server/app/backup.py`: source lease, `sqlite3.Connection.backup`, regular files only, versioned SHA-256 manifest, DB reference validation, fresh staging and atomic rename. CLI `python -m app.backup create DEST` / `restore BACKUP DEST`.
- [x] Run delivery and run regression tests and inspect backup contents for exclusion of keys/tests; commit scoped verified module changes under G2.

## Task 3: Installation and lifecycle

- [x] Add failing `server/tests/test_local_tools.py` tests for dependency preflight, pinned source preparation (local Git fixture only for mechanics), wrong/dirty checkout refusal, port conflict and process-owner matching.
- [x] Create `scripts/install.py`, `scripts/local.py`, and `.command` wrappers. Use checked argv subprocesses with timeouts, fixed HTTPS URL/Commit, two venvs with lockfiles, `npm ci` and build. No upstream setup scripts or auto model calls.
- [x] Launch the backend with built frontend on 127.0.0.1:8000; a foreground supervisor owns a control socket, children and cleanup. Stop via private local control socket, not stale PID alone. Keep readable runtime logs under var/local-delivery, honor absolute REPOLENS_DATA_DIR.
- [x] Run `server/.venv/bin/python -m pytest -q server/tests/test_local_tools.py server/tests/test_delivery.py` and `npm run build` in web.

## Task 4: Reproduction, UI and documentation

- [x] Commit G2 implementation, clone the local repository into a new ignored acceptance directory with spaces and install from scratch using official network sources; verify no dependency/upstream reuse by path.
- [x] Start/stop using .command entry, verify browser project import and stub run; back up actual saved data while stopped and restore to new directory, open M3 historical result/source in browser without model call.
- [x] Write `docs/05-local-setup-and-trial.md`, `evidence/m6/acceptance.md`, `evidence/m6/trial-observation-template.md`; update README/guide/roadmap with separate technical and user-trial statuses.
- [x] Run full backend tests, frontend build and browser critical flows; apply verification-before-completion, independent spec/standards code review and focused fixes.
- [x] G2 commit scoped evidence/docs, G3 ff-only merge to main, retain phase branch, no push; record post-merge smoke and 0/3 real users.

## Verification checkpoint

Final receipt: G3 fast-forwarded main to implementation/review-fix commit `0250f0c`; post-merge full backend 137 passed, final main-directory .command start/health/stop passed. Final review issues are closed. Technical delivery complete; real trial remains 0/3 and feedback iteration remains incomplete. The following paragraph records the earlier pre-merge checkpoint.

2026-09-22: implementation and independent task reviews complete. Full backend 135 passed, browser 26 passed, build passed. Fresh Git checkout installed from official fixed PocketFlow source with independent venvs; repeated installation and LaunchServices .command launch/stop passed. Actual 435-file data backup restored 2 projects, 3 runs and M3's 7 artifacts; browser reopened source and historical real output without a new model request. Final Node22 PATH regression: 17 local-tool tests passed. Remaining: final document/spec review, G2 evidence commit and G3 local merge. Real trial remains 0/3; no feedback iteration.
