from __future__ import annotations

import csv
import io
from pathlib import Path

from PySide6.QtWidgets import QApplication

from estimate_app.database.catalogue import CATALOGUE_HEADERS, CatalogueRepository
from estimate_app.database.connection import connect, initialise
from estimate_app.interface.catalogue_dialog import CatalogueDialog


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
