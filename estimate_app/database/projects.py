from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    id: int | None
    project_name: str
    scheme_id: str
    location: str
    client_department: str
    estimate_date: str
    correction_slip_cutoff_date: str


class ProjectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_projects(self) -> list[Project]:
        rows = self.connection.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, project_id: int) -> Project | None:
        row = self.connection.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return self._from_row(row) if row else None

    def save(self, project: Project) -> Project:
        values = (
            project.project_name,
            project.scheme_id,
            project.location,
            project.client_department,
            project.estimate_date,
            project.correction_slip_cutoff_date,
        )
        if project.id is None:
            cursor = self.connection.execute(
                """
                INSERT INTO projects (
                    project_name, scheme_id, location, client_department,
                    estimate_date, correction_slip_cutoff_date
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            project_id = cursor.lastrowid
        else:
            self.connection.execute(
                """
                UPDATE projects
                SET project_name = ?, scheme_id = ?, location = ?,
                    client_department = ?, estimate_date = ?,
                    correction_slip_cutoff_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                values + (project.id,),
            )
            project_id = project.id
        self.connection.commit()
        return self.get(project_id)  # type: ignore[arg-type]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            project_name=row["project_name"],
            scheme_id=row["scheme_id"],
            location=row["location"],
            client_department=row["client_department"],
            estimate_date=row["estimate_date"],
            correction_slip_cutoff_date=row["correction_slip_cutoff_date"],
        )
