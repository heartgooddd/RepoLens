# M5 Action Recipes Implementation Plan

> **For agentic workers:** Execute inline with test-driven development and final two-axis code review. User approved implementation and G2/G3; no additional approval checkpoint is needed.

**Goal:** Register the verified PocketFlow action and drive its form and isolated execution from a versioned recipe.

**Architecture:** Code-owned recipes define typed parameters, trusted entry, environment, input compatibility, timeout and artifacts. The runner resolves the recipe, binds a verified snapshot, applies a fail-closed macOS sandbox and persists recipe identity alongside existing history.

**Tech Stack:** Python/FastAPI/Pydantic/SQLite, macOS sandbox-exec, React/TypeScript, pytest/Playwright.

**Spec:** `docs/superpowers/specs/2026-09-22-m5-action-recipes-design.md`.

## Task 1: Registry and API contract

- [x] Add `server/tests/test_recipes.py`: assert `GET /api/recipes` returns only `pocketflow-tutorial`, a version, parameter schema, dependency state, fixed Commit, timeout/stop/output metadata; unknown recipe and arbitrary command requests fail before creating a run.
- [x] Run `server/.venv/bin/python -m pytest -q server/tests/test_recipes.py`; expect missing route/behavior failures.
- [x] Create `server/app/recipes/` with immutable recipe definitions, strict parameter models and registry lookup. Add migration 006 and recipe request dispatch in `run_api.py`; preserve legacy request compatibility through explicit fixed adapters, never arbitrary commands.
- [x] Add recipe identity and canonical parameter JSON to `Run`, persistence and cache identity. Test changing recipe version changes cache key and old nullable history remains readable.
- [x] Run recipe and existing run tests; inspect failures before adapting code.

## Task 2: Enforced isolation and lifecycle

- [x] Add `server/tests/test_isolation.py` and a no-network subprocess fixture. Assert allowed input read/output write, denied outside read/write, denied input modification, timeout, nonzero exit and child cleanup.
- [x] Run tests before creating `server/app/isolation.py`; expect missing implementation failures.
- [x] Implement explicit runtime/entry/input read paths and per-run writable paths, escaped sandbox literals, capability self-check, and fail-closed unsupported-platform behavior.
- [x] Integrate isolation into registered execution; retain trusted fixed entry independently of uploaded contents. Use recipe timeout and stop grace, preserve exit codes and descriptive failure categories, validate declared outputs.
- [x] Exercise actual pinned PocketFlow worker with the existing mock HTTP transport inside the sandbox. No paid model request.
- [x] Run `server/.venv/bin/python -m pytest -q server/tests`; expected all green, including old M3/M4 behavior.

## Task 3: Recipe-generated form

- [x] Add browser tests for recipe loading, generated field constraints, unavailable state and recipe metadata in history; watch missing UI assertions fail.
- [x] Add API recipe types and `RecipeFields.tsx`; update `TaskPanel.tsx` to render server-defined parameters and submit `recipe_id`, `snapshot_id`, `parameters`.
- [x] Keep existing explicitly labelled legacy diagnostic stub reachable; it is not a public registered recipe or third-party support evidence.
- [x] Run `npm run build` and `npm run test:e2e` from `web/`; expected typecheck/build and desktop/narrow tests pass.

## Task 4: Evidence, review and delivery

- [x] Write `docs/10-action-recipes.md`: exact recipe extension files, typed parameter example, environment/entry verification, isolation declaration, offline fixture tests, separate real verification and registration gate.
- [x] Record commands, counts, limitations, pinned worker identity and red/green observations in `evidence/m5/acceptance.md`. Update README, server README, guide, roadmap and architecture.
- [x] Verify migration idempotency, dependency checks, full backend suite, build, browser suite and `git diff --check`.
- [x] Commit only scoped files under G2; review against `eea0629` and the accepted spec on standards/spec axes. Fix material findings and run relevant regressions.
- [ ] With a clean branch and verified tree, fast-forward `main` per G3 and preserve the phase branch. No remote push.

## Progress

2026-09-22: Tasks 1–3 implemented and verified. Full backend 96 tests and browser 26 tests passed; final style/offline-label regression passed 4 browser cases. Task 4 documentation, evidence and two-axis independent review are complete. Review fixes bind each recipe's own upstream Commit to persistence, worker metadata and cache identity, and share artifact limit constants. Targeted backend regression covers these fixes and existing run/isolation behavior. Actual database migrated twice to version 6, old M3 success and 7 artifacts preserved. No paid model call. G3 remains the final delivery action after the review-fix G2 commit.
