"""Local snapshot APIs and registered isolated actions."""

import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, Settings
from .db import connect, migrate
from .data_lease import DataLease
from .models import Health, ProjectDetail, ProjectList
from .repository import get_project, list_projects
from .importer import ImportRequest, ImportResult, import_project
from .request_limits import ImportBodyLimit, ORIGINS
from .source import SourceSlice, read_source
from .runner import Runner
from .run_api import routes
from .github_importer import GitHubImporter, GitHubImportJob, GitHubImportRequest
from .import_policy import fail


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    runner = Runner(settings)
    github_importer = GitHubImporter(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with DataLease(settings.data_dir):
            settings.prepare()
            migrate(settings.database)
            try:
                runner.start()
                github_importer.start()
                yield
            finally:
                try:
                    await github_importer.close()
                finally:
                    await runner.close()

    app = FastAPI(title="RepoLens API", version="0.6.0", lifespan=lifespan)
    app.state.runner = runner
    app.state.github_importer = github_importer
    app.include_router(routes(settings, runner))
    app.add_middleware(ImportBodyLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_, exc):
        return JSONResponse(status_code=422, content={"detail": {"code": "invalid_request", "message": "请求字段不合法，请检查来源、文件数量、路径和参数。"}})

    @app.post("/api/projects/import", response_model=ImportResult, status_code=201)
    def import_repository(body: ImportRequest) -> ImportResult:
        return import_project(settings, body)

    @app.post("/api/github-imports", response_model=GitHubImportJob, status_code=202)
    async def start_github_import(body: GitHubImportRequest) -> GitHubImportJob:
        return github_importer.create(body.repository_url)

    @app.get("/api/github-imports/{job_id}", response_model=GitHubImportJob)
    def github_import(job_id: UUID) -> GitHubImportJob:
        result = github_importer.get(str(job_id))
        if result is None:
            fail("github_import_not_found", "远程导入任务不存在。", 404)
        return result

    @app.get("/api/snapshots/{snapshot_id}/source", response_model=SourceSlice)
    def source(snapshot_id: UUID, path: str, start: Annotated[int, Query(ge=1)] = 1,
               limit: Annotated[int, Query(ge=1, le=200)] = 80) -> SourceSlice:
        return read_source(settings, str(snapshot_id), path, start, limit)

    @app.get("/api/health", response_model=Health, responses={503: {"description": "Database unavailable"}})
    def health() -> Health:
        try:
            with connect(settings.database) as connection:
                version = connection.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
                connection.execute("SELECT id FROM projects LIMIT 1").fetchone()
                if version is None:
                    raise sqlite3.DatabaseError("Missing schema version")
            return Health(schema_version=version)
        except sqlite3.Error:
            raise HTTPException(status_code=503, detail="Database unavailable") from None

    @app.get("/api/projects", response_model=ProjectList)
    def projects(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> ProjectList:
        return list_projects(settings.database, limit, offset)

    @app.get("/api/projects/{project_id}", response_model=ProjectDetail, responses={404: {"description": "Project not found"}})
    def project(project_id: UUID) -> ProjectDetail:
        result = get_project(settings.database, str(project_id))
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return result

    if os.environ.get('REPOLENS_SERVE_WEB') == '1':
        @app.api_route('/api/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'], include_in_schema=False)
        def missing_api(path: str):
            return JSONResponse(status_code=404, content={'detail': 'Not Found'})

        app.mount('/', StaticFiles(directory=ROOT / 'web' / 'dist', html=True), name='web')

    return app


app = create_app()
