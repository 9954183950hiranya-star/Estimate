from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


APP_DIRECTORY_NAME = "BuildingEstimate"


def user_data_directory() -> Path:
    """Return a writable per-user directory outside the application files."""
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if root:
            return Path(root) / APP_DIRECTORY_NAME
        return Path.home() / "AppData" / "Local" / APP_DIRECTORY_NAME

    root = os.environ.get("XDG_DATA_HOME")
    if root:
        return Path(root) / APP_DIRECTORY_NAME
    return Path.home() / ".local" / "share" / APP_DIRECTORY_NAME


def database_path() -> Path:
    return user_data_directory() / "estimate.sqlite3"


def connect(path: Path | None = None) -> sqlite3.Connection:
    database = path or database_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialise(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            scheme_id TEXT NOT NULL,
            location TEXT NOT NULL,
            client_department TEXT NOT NULL,
            estimate_date TEXT NOT NULL,
            correction_slip_cutoff_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()
