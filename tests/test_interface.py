from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from estimate_app.database.connection import connect, initialise
from estimate_app.database.projects import Project, ProjectRepository
from estimate_app.interface.main_window import MainWindow


@pytest.fixture
def window(tmp_path: Path) -> tuple[MainWindow, sqlite3.Connection]:
    connection = connect(tmp_path / "isolated.sqlite3")
    initialise(connection)
    application = QApplication.instance() or QApplication([])
    result = MainWindow(ProjectRepository(connection))
    result._test_application = application
    yield result, connection
    result.close()
    connection.close()


def fill_project(window: MainWindow, name: str = "School Building") -> None:
    window.project_name.setText(name)
    window.scheme_id.setText("SCH-001")
    window.location.setText("Delhi")
    window.client_department.setText("Education Department")
    window.estimate_date.setDate(QDate(2026, 9, 24))
    window.cutoff_date.setDate(QDate(2026, 8, 31))


def test_headless_window_has_expected_title_and_closes(window: tuple[MainWindow, sqlite3.Connection]) -> None:
    main_window, _ = window
    assert main_window.windowTitle() == "Building Estimate — CPWD DSR 2023"
    main_window._test_application.processEvents()


def test_blank_project_name_is_rejected(
    window: tuple[MainWindow, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    main_window, connection = window
    fill_project(main_window)
    main_window.project_name.clear()
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(str(args[2])))

    main_window._save_project()

    assert "Project / scheme name" in messages[0]
    assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_cutoff_after_estimate_is_rejected(
    window: tuple[MainWindow, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    main_window, connection = window
    fill_project(main_window)
    main_window.cutoff_date.setDate(QDate(2026, 10, 1))
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(str(args[2])))

    main_window._save_project()

    assert "cannot be after" in messages[0]
    assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_project_fields_save_reopen_and_duplicate_names_do_not_overwrite(
    window: tuple[MainWindow, sqlite3.Connection]
) -> None:
    main_window, connection = window
    fill_project(main_window)
    main_window._save_project()
    first_id = main_window.current_project_id
    main_window._new_project()
    fill_project(main_window)
    main_window.scheme_id.setText("SCH-002")
    main_window._save_project()

    rows = connection.execute(
        "SELECT id, project_name, scheme_id FROM projects ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["id"] == first_id
    assert rows[0]["scheme_id"] == "SCH-001"
    assert rows[1]["scheme_id"] == "SCH-002"

    for index in range(main_window.project_list.count()):
        item = main_window.project_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == first_id:
            main_window.project_list.setCurrentItem(item)
            break
    assert main_window.project_name.text() == "School Building"
    assert main_window.scheme_id.text() == "SCH-001"
    assert main_window.location.text() == "Delhi"
    assert main_window.client_department.text() == "Education Department"
    assert main_window.estimate_date.date() == QDate(2026, 9, 24)
    assert main_window.cutoff_date.date() == QDate(2026, 8, 31)


def test_database_error_is_reported(
    window: tuple[MainWindow, sqlite3.Connection], monkeypatch: pytest.MonkeyPatch
) -> None:
    main_window, connection = window
    fill_project(main_window)
    connection.close()
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: messages.append(str(args[2])))

    main_window._save_project()

    assert messages
    assert "Project could not be saved" in messages[0]


def test_boq_screen_saves_measurements_and_recalculates(
    window: tuple[MainWindow, sqlite3.Connection]
) -> None:
    main_window, connection = window
    project = ProjectRepository(connection).save(
        Project(None, "Synthetic BOQ Project", "TEST-BOQ", "Delhi", "Test Department", "2026-09-24", "2026-08-31")
    )
    editor = main_window.boq_editor
    editor.set_project(project.id)
    editor.work_section.setText("Concrete")
    editor.dsr_item_code.setText("TEST-RATE-001")
    editor.description.setText("Synthetic test concrete")
    editor.unit.setText("cum")
    editor.rate.setText("100.00")
    editor._save_item()

    editor.particulars.setText("Foundation addition")
    editor.repetitions.setText("1")
    editor.number.setText("4")
    editor.length.setText("2")
    editor.breadth.setText("1.5")
    editor.height_depth.setText("0.5")
    editor._save_measurement()
    editor._new_measurement()
    editor.particulars.setText("Opening deduction")
    editor.is_deduction.setChecked(True)
    editor.repetitions.setText("1")
    editor.number.setText("2")
    editor.length.setText("0.5")
    editor.breadth.setText("0.5")
    editor.height_depth.setText("0.5")
    editor._save_measurement()

    assert editor.measurement_table.rowCount() == 2
    assert "Net 5.750" in editor.summary_label.text()
    assert "₹575.00" in editor.summary_label.text()
    assert connection.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 2
