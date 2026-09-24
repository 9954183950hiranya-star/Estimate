from decimal import Decimal
from pathlib import Path

import pytest

from estimate_app.calculation.decimal_policy import MeasurementType, MeasurementValues
from estimate_app.database.boq import (
    BOQItem,
    BOQRepository,
    Measurement,
    UnitChangeRequiresResolution,
)
from estimate_app.database.connection import connect, initialise
from estimate_app.database.projects import Project, ProjectRepository


def project_and_repository(tmp_path: Path) -> tuple[Project, BOQRepository]:
    connection = connect(tmp_path / "estimate.sqlite3")
    initialise(connection)
    project = ProjectRepository(connection).save(
        Project(None, "Synthetic Test Project", "TEST-001", "Delhi", "Test Department", "2026-09-24", "2026-08-31")
    )
    return project, BOQRepository(connection)


def make_item(project: Project, repository: BOQRepository, unit: str = "cum", rate: Decimal | None = Decimal("100")):
    return repository.save_item(
        BOQItem(None, project.id, 1, "Concrete", "TEST-RATE-001", "Synthetic test data", unit, MeasurementType.VOLUME, rate)
    )


def test_migration_preserves_existing_project_and_isolates_boq(tmp_path: Path) -> None:
    connection = connect(tmp_path / "migration.sqlite3")
    initialise(connection)
    project_a = ProjectRepository(connection).save(Project(None, "Existing A", "A", "A", "A", "2026-09-24", "2026-08-31"))
    project_b = ProjectRepository(connection).save(Project(None, "Existing B", "B", "B", "B", "2026-09-24", "2026-08-31"))
    repository = BOQRepository(connection)
    repository.save_item(BOQItem(None, project_a.id, 1, "Earthwork", "TEST-A", "A", "cum", MeasurementType.VOLUME, Decimal("1")))
    assert [project.project_name for project in ProjectRepository(connection).list_projects()] == ["Existing B", "Existing A"]
    assert len(repository.list_items(project_a.id)) == 1
    assert repository.list_items(project_b.id) == []


def test_measurements_persist_edit_delete_and_unit_change_requires_resolution(tmp_path: Path) -> None:
    project, repository = project_and_repository(tmp_path)
    item = make_item(project, repository)
    measurement = repository.save_measurement(
        Measurement(None, item.id, "Foundation", False, MeasurementType.VOLUME, MeasurementValues(Decimal("1"), Decimal("1"), Decimal("2"), Decimal("2"), Decimal("2")), "initial")
    )
    edited = repository.save_measurement(
        Measurement(measurement.id, item.id, "Foundation revised", False, MeasurementType.VOLUME, MeasurementValues(Decimal("1"), Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2")), "edited")
    )
    assert repository.list_measurements(item.id)[0] == edited
    with pytest.raises(UnitChangeRequiresResolution):
        repository.save_item(BOQItem(item.id, project.id, 1, "Concrete", "TEST-RATE-001", "Synthetic test data", "sqm", MeasurementType.AREA, Decimal("100")))
    changed = repository.save_item(BOQItem(item.id, project.id, 1, "Concrete", "TEST-RATE-001", "Synthetic test data", "sqm", MeasurementType.AREA, Decimal("100")), resolve_unit_change=True)
    assert changed.unit == "sqm"
    assert repository.list_measurements(item.id) == []
    repository.save_measurement(Measurement(None, item.id, "Delete me", False, MeasurementType.AREA, MeasurementValues(Decimal("1"), Decimal("1"), Decimal("2"), Decimal("2"))))
    measurement_id = repository.list_measurements(item.id)[0].id
    repository.delete_measurement(measurement_id)
    assert repository.list_measurements(item.id) == []


def test_missing_and_zero_rates_and_negative_quantity_are_distinct(tmp_path: Path) -> None:
    project, repository = project_and_repository(tmp_path)
    missing = make_item(project, repository, rate=None)
    zero = repository.save_item(BOQItem(None, project.id, 2, "Count", "TEST-ZERO", "Zero rate test", "each", MeasurementType.COUNT, Decimal("0")))
    measurement = Measurement(None, missing.id, "Deduction", True, MeasurementType.COUNT, MeasurementValues(Decimal("1"), Decimal("1")))
    repository.save_measurement(measurement)
    missing_summary = repository.summary(missing.id)
    assert missing_summary.rate_missing and missing_summary.amount is None
    repository.save_measurement(Measurement(None, zero.id, "Count", False, MeasurementType.COUNT, MeasurementValues(Decimal("1"), Decimal("2"))))
    zero_summary = repository.summary(zero.id)
    assert not zero_summary.rate_missing and zero_summary.amount == Decimal("0.00")
    assert zero_summary.totals is not None
    assert missing_summary.totals is not None and missing_summary.totals.has_negative_net
