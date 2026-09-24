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
        CREATE TABLE IF NOT EXISTS boq_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            serial_number INTEGER NOT NULL,
            work_section TEXT NOT NULL,
            dsr_item_code TEXT NOT NULL,
            description TEXT NOT NULL,
            unit TEXT NOT NULL,
            quantity_type TEXT NOT NULL,
            rate TEXT,
            rate_source TEXT NOT NULL,
            verification_status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, serial_number)
        );
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_item_id INTEGER NOT NULL REFERENCES boq_items(id) ON DELETE CASCADE,
            particulars TEXT NOT NULL,
            is_deduction INTEGER NOT NULL DEFAULT 0 CHECK (is_deduction IN (0, 1)),
            measurement_type TEXT NOT NULL,
            repetitions TEXT,
            number TEXT,
            length TEXT,
            breadth TEXT,
            height_depth TEXT,
            direct_quantity TEXT,
            remarks TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_boq_items_project ON boq_items(project_id, serial_number);
        CREATE INDEX IF NOT EXISTS idx_measurements_item ON measurements(boq_item_id, id);
        CREATE TABLE IF NOT EXISTS catalogue_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_name TEXT NOT NULL,
            edition TEXT NOT NULL,
            volume TEXT NOT NULL,
            chapter TEXT NOT NULL,
            item_code TEXT NOT NULL,
            parent_item_code TEXT,
            description TEXT NOT NULL,
            original_unit TEXT NOT NULL,
            canonical_unit TEXT NOT NULL,
            original_rate TEXT,
            source_document_name TEXT NOT NULL,
            source_page INTEGER NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'Unverified',
            reviewer TEXT,
            verification_date TEXT,
            is_heading INTEGER NOT NULL DEFAULT 0 CHECK (is_heading IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(schedule_name, edition, item_code)
        );
        CREATE INDEX IF NOT EXISTS idx_catalogue_search_code ON catalogue_items(item_code);
        CREATE INDEX IF NOT EXISTS idx_catalogue_search_description ON catalogue_items(description);
        CREATE TABLE IF NOT EXISTS catalogue_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file_name TEXT NOT NULL,
            source_checksum TEXT NOT NULL UNIQUE,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_summary TEXT
        );
        CREATE TABLE IF NOT EXISTS correction_slips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slip_reference TEXT NOT NULL,
            publication_date TEXT NOT NULL,
            effective_date TEXT NOT NULL,
            effective_date_source TEXT NOT NULL,
            item_code TEXT NOT NULL,
            operation TEXT NOT NULL CHECK (operation IN ('add', 'amend', 'delete')),
            changed_parent_item_code TEXT,
            changed_description TEXT,
            changed_original_unit TEXT,
            changed_canonical_unit TEXT,
            changed_rate TEXT,
            changed_volume TEXT,
            changed_chapter TEXT,
            source_document_name TEXT NOT NULL,
            source_page INTEGER NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'Unverified',
            reviewer TEXT,
            verification_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(slip_reference, item_code, operation)
        );
        CREATE INDEX IF NOT EXISTS idx_corrections_item ON correction_slips(item_code, effective_date);
        """
    )
    _add_column_if_missing(connection, "boq_items", "catalogue_item_id", "INTEGER")
    _add_column_if_missing(connection, "boq_items", "catalogue_version_id", "INTEGER")
    _add_column_if_missing(connection, "boq_items", "manual_override_reason", "TEXT")
    connection.execute("PRAGMA user_version = 3")
    connection.commit()


def _add_column_if_missing(
    connection: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
