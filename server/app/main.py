"""Read-only API foundation; import and run endpoints arrive in later milestones."""

import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .db import connect, migrate
from .models import Health, ProjectDetail, ProjectList
from .repository import get_project, list_projects


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.prepare()
        migrate(settings.database)
        yield

    app = FastAPI(title="RepoLens API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

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

    return app


app = create_app()
