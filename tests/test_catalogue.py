from __future__ import annotations

import csv
import io
from decimal import Decimal
from pathlib import Path

import pytest

from estimate_app.calculation.decimal_policy import MeasurementType
from estimate_app.database.boq import BOQItem, BOQRepository
from estimate_app.database.catalogue import (
    CATALOGUE_HEADERS,
    CORRECTION_HEADERS,
    VERIFIED,
    CatalogueImportError,
    CatalogueRepository,
    ConflictingCorrectionsError,
    CorrectionSlip,
    blank_catalogue_template,
)
from estimate_app.database.connection import connect, initialise
from estimate_app.database.projects import Project, ProjectRepository


def catalogue_csv(*rows: dict[str, str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CATALOGUE_HEADERS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def row(code: str = "1.1", **overrides: str) -> dict[str, str]:
    values = {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earthwork",
        "item_code": code,
        "parent_item_code": "",
        "description": "Excavation in ordinary soil",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "100.00",
        "source_document_name": "synthetic-dsr-test.csv",
        "source_page": "10",
        "is_heading": "false",
    }
    values.update(overrides)
    return values


def make_repository(tmp_path: Path) -> CatalogueRepository:
    connection = connect(tmp_path / "catalogue.sqlite3")
    initialise(connection)
    return CatalogueRepository(connection)


def verify(repository: CatalogueRepository, item_code: str, reviewer: str = "Test reviewer") -> None:
    item = next(item for item in repository.list_items() if item.item_code == item_code)
    repository.verify_item(item.id, reviewer, "2026-09-24")


def test_import_parent_inheritance_is_unverified_and_repeat_is_safe(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    content = catalogue_csv(
        row("1", description="Earthwork", rate="", is_heading="true"),
        row("1.1", parent_item_code="1", description="Excavation", rate="100.00"),
    )
    first = repository.import_csv(io.StringIO(content), "synthetic.csv")
    repeated = repository.import_csv(io.StringIO(content), "different-name.csv")
    repeated_with_different_line_endings = repository.import_csv(io.StringIO(content.replace("\n", "\r\n")), "line-endings.csv")
    child = next(item for item in repository.list_items() if item.item_code == "1.1")

    assert first.status == "Imported"
    assert repeated.id == first.id
    assert repeated_with_different_line_endings.row_count == 2
    assert len(repository.list_items()) == 2
    assert child.description == "Earthwork — Excavation"
    assert child.verification_status != VERIFIED
    assert child.is_heading is False
    assert blank_catalogue_template().splitlines()[0].split(",") == list(CATALOGUE_HEADERS)


def test_heading_rows_without_units_or_rates_are_valid(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    content = catalogue_csv(
        row("0.1", description="HIRE CHARGES OF PLANTS & MACHINERY", rate="", is_heading="true", original_unit="", canonical_unit=""),
        row("0001", parent_item_code="0.1", description="Hire charges of Coaltar Boiler 900 to 1400 litres", rate="900.00", original_unit="day", canonical_unit="day"),
    )

    preview = repository.preview_csv(io.StringIO(content), "synthetic-heading.csv")

    assert preview.errors == ()
    assert preview.rows[0].is_heading is True
    assert preview.rows[0].original_unit == ""
    assert preview.rows[0].canonical_unit == ""


def test_invalid_import_rolls_back_all_rows_and_reports_row_errors(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    content = catalogue_csv(row("2.1"), row("2.2", rate="not-a-rate"))

    with pytest.raises(CatalogueImportError) as error:
        repository.import_csv(io.StringIO(content), "invalid.csv")

    assert "row 3" in str(error.value)
    assert repository.list_items() == []
    assert repository.list_imports() == []


def test_conflicting_existing_record_rolls_back_new_records(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.import_csv(io.StringIO(catalogue_csv(row("3.1"))), "first.csv")
    conflicting = catalogue_csv(row("3.2"), row("3.1", rate="999.00"))

    with pytest.raises(CatalogueImportError):
        repository.import_csv(io.StringIO(conflicting), "conflict.csv")

    assert {item.item_code for item in repository.list_items()} == {"3.1"}
    assert len(repository.list_imports()) == 1


def test_unverified_items_are_not_selectable_until_explicitly_verified(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.import_csv(io.StringIO(catalogue_csv(row("4.1"))), "verified-later.csv")
    assert repository.search(query="4.1") == []
    verify(repository, "4.1")
    results = repository.search(query="4.1")
    assert len(results) == 1
    assert results[0].item.rate == Decimal("100.00")
    assert results[0].item.verification_status == VERIFIED


def test_corrections_resolve_before_on_after_cutoff_and_retain_fields(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.import_csv(io.StringIO(catalogue_csv(row("5.1"))), "corrections.csv")
    verify(repository, "5.1")
    corrections = [
        CorrectionSlip(None, "CS-001", "2023-01-01", "2023-02-01", "synthetic notice p. 1", "5.1", "amend", "slip.pdf", 1, changed_description="Amended description"),
        CorrectionSlip(None, "CS-002", "2024-01-01", "2024-02-01", "synthetic notice p. 2", "5.1", "amend", "slip.pdf", 2, changed_rate=Decimal("110.00")),
        CorrectionSlip(None, "CS-003", "2027-01-01", "2027-02-01", "synthetic notice p. 3", "5.1", "amend", "slip.pdf", 3, changed_rate=Decimal("120.00")),
    ]
    for correction in corrections:
        created = repository.add_correction(correction)
        repository.verify_correction(created.id, "Correction reviewer", "2027-03-01")

    before_cutoff = repository.resolve_item("CPWD DSR Civil", "2023", "5.1", "2023-12-31")
    on_cutoff = repository.resolve_item("CPWD DSR Civil", "2023", "5.1", "2024-02-01")
    after_cutoff = repository.resolve_item("CPWD DSR Civil", "2023", "5.1", "2027-12-31")
    assert before_cutoff.item.description == "Amended description"
    assert before_cutoff.item.rate == Decimal("100.00")
    assert on_cutoff.item.rate == Decimal("110.00")
    assert on_cutoff.item.original_unit == "cum"
    assert after_cutoff.item.rate == Decimal("120.00")
    assert len(on_cutoff.applied_corrections) == 2


def test_added_and_deleted_corrections_and_conflicts(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    added = repository.add_correction(
        CorrectionSlip(None, "CS-ADD", "2024-01-01", "2024-02-01", "synthetic add p. 1", "6.1", "add", "slip.pdf", 1, changed_description="Added item", changed_original_unit="sqm", changed_canonical_unit="sqm", changed_rate=Decimal("50.00"), changed_volume="Volume 2", changed_chapter="Concrete")
    )
    repository.verify_correction(added.id, "Reviewer", "2024-03-01")
    added_result = repository.resolve_item("CPWD DSR Civil", "2023", "6.1", "2024-12-31")
    assert added_result.item.description == "Added item"
    assert added_result.item.rate == Decimal("50.00")
    assert [result.item.item_code for result in repository.search(query="6.1", cutoff_date="2024-12-31")] == ["6.1"]

    repository.import_csv(io.StringIO(catalogue_csv(row("6.2"))), "delete.csv")
    verify(repository, "6.2")
    deleted = repository.add_correction(CorrectionSlip(None, "CS-DEL", "2024-01-01", "2024-02-01", "synthetic delete p. 2", "6.2", "delete", "slip.pdf", 2))
    repository.verify_correction(deleted.id, "Reviewer", "2024-03-01")
    assert repository.resolve_item("CPWD DSR Civil", "2023", "6.2", "2024-12-31").deleted

    first = repository.add_correction(CorrectionSlip(None, "CS-C1", "2024-01-01", "2025-01-01", "source", "6.2", "amend", "slip.pdf", 3, changed_rate=Decimal("70")))
    second = repository.add_correction(CorrectionSlip(None, "CS-C2", "2024-01-02", "2025-01-01", "source", "6.2", "amend", "slip.pdf", 4, changed_rate=Decimal("80")))
    repository.verify_correction(first.id, "Reviewer", "2025-02-01")
    repository.verify_correction(second.id, "Reviewer", "2025-02-01")
    with pytest.raises(ConflictingCorrectionsError):
        repository.resolve_item("CPWD DSR Civil", "2023", "6.2", "2025-12-31")


def test_existing_boq_snapshot_does_not_change_after_catalogue_update(tmp_path: Path) -> None:
    connection = connect(tmp_path / "snapshot.sqlite3")
    initialise(connection)
    catalogue = CatalogueRepository(connection)
    catalogue.import_csv(io.StringIO(catalogue_csv(row("7.1"))), "snapshot.csv")
    verify(catalogue, "7.1")
    catalog_item = catalogue.search(query="7.1")[0].item
    project = ProjectRepository(connection).save(Project(None, "Snapshot Project", "S", "Delhi", "PWD", "2026-09-24", "2026-08-31"))
    boq = BOQRepository(connection)
    snapshot = boq.save_item(BOQItem(None, project.id, 1, "Earthwork", catalog_item.item_code, catalog_item.description, catalog_item.canonical_unit, MeasurementType.VOLUME, catalog_item.rate, "synthetic-dsr-test.csv, p. 10", VERIFIED, catalog_item.id, catalog_item.id))
    correction = catalogue.add_correction(CorrectionSlip(None, "CS-SNAPSHOT", "2024-01-01", "2024-02-01", "source", "7.1", "amend", "slip.pdf", 5, changed_rate=Decimal("999")))
    catalogue.verify_correction(correction.id, "Reviewer", "2024-03-01")
    assert boq.get_item(snapshot.id).rate == Decimal("100.00")


def test_correction_csv_import_is_unverified_and_repeat_safe(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CORRECTION_HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerow({
        "slip_reference": "CSV-CS-1", "publication_date": "2026-01-01", "effective_date": "2026-02-01",
        "effective_date_source": "synthetic correction p. 1", "item_code": "CSV-1", "operation": "add",
        "changed_parent_item_code": "", "changed_description": "CSV added item", "changed_original_unit": "cum",
        "changed_canonical_unit": "cum", "changed_rate": "25.00", "changed_volume": "Volume 1",
        "changed_chapter": "Concrete", "source_document_name": "synthetic-correction.csv", "source_page": "1",
    })
    content = output.getvalue()
    first = repository.import_correction_csv(io.StringIO(content), "corrections.csv")
    repeated = repository.import_correction_csv(io.StringIO(content), "other-name.csv")
    assert first.id == repeated.id
    assert repository.list_corrections()[0].verification_status == "Unverified"
    assert repository.search(query="CSV-1", cutoff_date="2026-12-31") == []