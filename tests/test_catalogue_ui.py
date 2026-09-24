from __future__ import annotations

import csv
import io
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from estimate_app.calculation.decimal_policy import MeasurementType
from estimate_app.database.boq import BOQItem, BOQRepository
from estimate_app.database.catalogue import CATALOGUE_HEADERS, CatalogueRepository, CorrectionSlip
from estimate_app.database.connection import connect, initialise
from estimate_app.database.projects import Project, ProjectRepository
from estimate_app.interface.catalogue_dialog import CatalogueDialog
from estimate_app.interface.review_dialogs import CatalogueReviewDialog, CorrectionReviewDialog


def test_headless_catalogue_search_shows_verified_item(tmp_path: Path) -> None:
    connection = connect(tmp_path / "catalogue-ui.sqlite3")
    initialise(connection)
    repository = CatalogueRepository(connection)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CATALOGUE_HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(
        {
            "schedule_name": "CPWD DSR Civil",
            "edition": "2023",
            "volume": "Volume 1",
            "chapter": "Concrete",
            "item_code": "UI-1",
            "parent_item_code": "",
            "description": "Synthetic verified concrete",
            "original_unit": "cum",
            "canonical_unit": "cum",
            "rate": "100.00",
            "source_document_name": "synthetic-ui.csv",
            "source_page": "7",
            "is_heading": "false",
        }
    )
    repository.import_csv(io.StringIO(output.getvalue()), "synthetic-ui.csv")
    item = repository.list_items(include_headings=False)[0]
    repository.verify_item(item.id, "UI reviewer", "2026-09-24")

    application = QApplication.instance() or QApplication([])
    dialog = CatalogueDialog(repository, "2026-09-24")
    assert dialog.results.rowCount() == 1
    assert dialog.results.item(0, 7).text() == "synthetic-ui.csv, p. 7"
    dialog.results.selectRow(0)
    dialog._accept_selection()
    assert dialog.selected is not None
    assert dialog.selected.item.item_code == "UI-1"
    dialog.close()
    application.processEvents()
    connection.close()


def _add_item(repository: CatalogueRepository, code: str = "UI-REVIEW") -> int:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CATALOGUE_HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerow({
        "schedule_name": "CPWD DSR Civil", "edition": "2023", "volume": "Volume 1",
        "chapter": "Concrete", "item_code": code, "parent_item_code": "",
        "description": "Synthetic review item", "original_unit": "cum", "canonical_unit": "cum",
        "rate": "100.00", "source_document_name": "synthetic-review.pdf", "source_page": "8", "is_heading": "false",
    })
    repository.import_csv(io.StringIO(output.getvalue()), "synthetic-review.csv")
    return repository.list_items(include_headings=False)[-1].id


def test_review_dialog_requires_explicit_verification_before_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    connection = connect(tmp_path / "review.sqlite3")
    initialise(connection)
    repository = CatalogueRepository(connection)
    item_id = _add_item(repository)
    application = QApplication.instance() or QApplication([])
    review = CatalogueReviewDialog(repository)
    assert review.table.rowCount() == 1
    review.table.selectRow(0)
    selector_before = CatalogueDialog(repository, "2026-09-24")
    assert selector_before.results.rowCount() == 0
    selector_before.close()
    answers = iter([("Reviewer", True), ("2026-09-24", True)])
    monkeypatch.setattr("estimate_app.interface.review_dialogs.QInputDialog.getText", lambda *args: next(answers))
    review._verify()
    assert repository.get_item(item_id).verification_status == "Verified"
    selector_after = CatalogueDialog(repository, "2026-09-24")
    assert selector_after.results.rowCount() == 1
    selector_after.close()
    review.close()
    application.processEvents()
    connection.close()


def test_correction_review_draft_then_verified_cutoff_and_withdrawal_flags_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    connection = connect(tmp_path / "correction-review.sqlite3")
    initialise(connection)
    repository = CatalogueRepository(connection)
    item_id = _add_item(repository, "UI-CORRECTION")
    item = repository.get_item(item_id)
    repository.verify_item(item_id, "Base reviewer", "2026-09-24")
    project = ProjectRepository(connection).save(Project(None, "Review snapshot", "R", "Delhi", "PWD", "2026-09-24", "2026-08-31"))
    snapshot = BOQRepository(connection).save_item(BOQItem(None, project.id, 1, "Concrete", item.item_code, item.description, item.canonical_unit, MeasurementType.VOLUME, item.rate, "synthetic-review.pdf, p. 8", "Verified", item.id, item.id))
    application = QApplication.instance() or QApplication([])
    dialog = CorrectionReviewDialog(repository)
    dialog.slip_reference.setText("UI-CS-1")
    dialog.publication_date.setText("2026-01-01")
    dialog.effective_date.setText("2026-02-01")
    dialog.effective_date_source.setText("synthetic notice p. 1")
    dialog.item_code.setText(item.item_code)
    dialog.operation.setCurrentText("amend")
    dialog.source_document.setText("synthetic-correction.pdf")
    dialog.source_page.setText("2")
    dialog.changed_rate.setText("110.00")
    dialog._save_draft()
    assert repository.resolve_item("CPWD DSR Civil", "2023", item.item_code, "2026-01-31").item.rate == Decimal("100.00")
    dialog.table.selectRow(0)
    answers = iter([("Correction reviewer", True), ("2026-09-24", True)])
    monkeypatch.setattr("estimate_app.interface.review_dialogs.QInputDialog.getText", lambda *args: next(answers))
    dialog._verify()
    assert repository.resolve_item("CPWD DSR Civil", "2023", item.item_code, "2026-02-01").item.rate == Decimal("110.00")
    dialog.table.selectRow(0)
    answers = iter([("Correction reviewer", True), ("2026-09-25", True), ("source mistake", True)])
    monkeypatch.setattr("estimate_app.interface.review_dialogs.QInputDialog.getText", lambda *args: next(answers))
    dialog._withdraw()
    assert repository.search(query=item.item_code, cutoff_date="2026-12-31")
    catalogue_review = CatalogueReviewDialog(repository)
    catalogue_review.table.selectRow(0)
    answers = iter([("Catalogue reviewer", True), ("2026-09-26", True), ("source mistake", True)])
    monkeypatch.setattr("estimate_app.interface.review_dialogs.QInputDialog.getText", lambda *args: next(answers))
    catalogue_review._withdraw()
    assert repository.search(query=item.item_code, cutoff_date="2026-12-31") == []
    saved_snapshot = BOQRepository(connection).get_item(snapshot.id)
    assert saved_snapshot.rate == Decimal("100.00")
    assert saved_snapshot.needs_catalogue_review is True
    catalogue_review.close()
    dialog.close()
    application.processEvents()
    connection.close()


def test_missing_reference_pdf_is_readable(tmp_path: Path) -> None:
    connection = connect(tmp_path / "documents.sqlite3")
    initialise(connection)
    repository = CatalogueRepository(connection)
    with pytest.raises(FileNotFoundError, match="not found"):
        repository.attach_reference_document(tmp_path / "missing.pdf")
    connection.close()
