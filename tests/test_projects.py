from pathlib import Path

from estimate_app.database.connection import connect, database_path, initialise
from estimate_app.database.projects import Project, ProjectRepository


def test_project_is_saved_and_reopened_from_a_new_connection(tmp_path: Path) -> None:
    path = tmp_path / "data" / "estimate.sqlite3"
    first_connection = connect(path)
    initialise(first_connection)
    repository = ProjectRepository(first_connection)
    saved = repository.save(
        Project(
            id=None,
            project_name="District Office",
            scheme_id="DO-001",
            location="Bhopal",
            client_department="Public Works Department",
            estimate_date="2026-09-24",
            correction_slip_cutoff_date="2026-08-31",
        )
    )
    first_connection.close()

    second_connection = connect(path)
    reopened = ProjectRepository(second_connection).get(saved.id)
    second_connection.close()

    assert reopened == saved
    assert path.exists()


def test_default_database_is_outside_the_source_tree() -> None:
    assert database_path().parent.name == "BuildingEstimate"
    assert "estimate_app" not in database_path().parts
