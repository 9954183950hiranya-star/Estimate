from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from estimate_app.database.catalogue import (
    CatalogueImportError,
    CatalogueRepository,
    ResolvedCatalogueItem,
    blank_catalogue_template,
)


class CatalogueDialog(QDialog):
    def __init__(self, repository: CatalogueRepository, cutoff_date: str | None, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.cutoff_date = cutoff_date
        self.selected: ResolvedCatalogueItem | None = None
        self.setWindowTitle("Select verified CPWD DSR 2023 item")
        self.resize(1100, 620)
        self._build_ui()
        self._load_filters()
        self._search()

    def _build_ui(self) -> None:
        self.search_text = QLineEdit()
        self.search_text.setPlaceholderText("Search code or description")
        self.volume = QComboBox()
        self.chapter = QComboBox()
        self.unit = QComboBox()
        for combo in (self.volume, self.chapter, self.unit):
            combo.addItem("All", "")
            combo.currentIndexChanged.connect(self._search)
        self.search_text.textChanged.connect(self._search)
        search_form = QFormLayout()
        search_form.addRow("Code / description", self.search_text)
        search_form.addRow("Volume", self.volume)
        search_form.addRow("Chapter", self.chapter)
        search_form.addRow("Canonical unit", self.unit)

        self.results = QTableWidget(0, 9)
        self.results.setHorizontalHeaderLabels(
            ["Code", "Volume", "Chapter", "Description", "Unit", "Original rate", "Corrected rate", "Source", "Status"]
        )
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results.itemDoubleClicked.connect(lambda _: self._accept_selection())
        self.coverage = QLabel()
        select_button = QPushButton("Select verified item")
        select_button.clicked.connect(self._accept_selection)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        import_button = QPushButton("Preview and import CSV")
        import_button.clicked.connect(self._import_csv)
        export_button = QPushButton("Export blank template")
        export_button.clicked.connect(self._export_template)
        buttons = QDialogButtonBox()
        buttons.addButton(import_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(export_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(select_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout = QVBoxLayout(self)
        layout.addLayout(search_form)
        layout.addWidget(self.coverage)
        layout.addWidget(self.results)
        layout.addWidget(buttons)

    def _load_filters(self) -> None:
        items = self.repository.list_items(include_headings=False)
        for combo, values in (
            (self.volume, sorted({item.volume for item in items})),
            (self.chapter, sorted({item.chapter for item in items})),
            (self.unit, sorted({item.canonical_unit for item in items})),
        ):
            combo.blockSignals(True)
            combo.addItems(values)
            combo.blockSignals(False)
        coverage = self.repository.coverage_summary()
        self.coverage.setText(
            f"Recorded catalogue coverage: {coverage['record_count']} records, "
            f"{coverage['verified_count']} verified. {coverage['coverage_note']}"
        )

    def _search(self) -> None:
        results = self.repository.search(
            query=self.search_text.text().strip(),
            volume=self.volume.currentData() or "",
            chapter=self.chapter.currentData() or "",
            unit=self.unit.currentData() or "",
            cutoff_date=self.cutoff_date,
        )
        self.results.setRowCount(0)
        for resolved in results:
            item = resolved.item
            row = self.results.rowCount()
            self.results.insertRow(row)
            original = self.repository.get_item(item.id) if item.id is not None else None
            original_rate = "" if original is None or original.rate is None else f"₹{original.rate:.2f}"
            latest_rate = "" if item.rate is None else f"₹{item.rate:.2f}"
            source = f"{item.source_document_name}, p. {item.source_page}"
            values = [item.item_code, item.volume, item.chapter, item.description, item.canonical_unit, original_rate, latest_rate, source, item.verification_status]
            for column, value in enumerate(values):
                self.results.setItem(row, column, QTableWidgetItem(value))
            self.results.item(row, 0).setData(Qt.ItemDataRole.UserRole, resolved)

    def _export_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export blank catalogue template", "cpwd_dsr_catalogue_template.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(blank_catalogue_template())
        except OSError as error:
            QMessageBox.critical(self, "Template export failed", str(error))

    def _import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import catalogue CSV", "", "CSV files (*.csv)")
        if not path:
            return
        preview = self.repository.preview_csv(path)
        if preview.errors:
            QMessageBox.warning(self, "Import validation failed", "\n".join(preview.errors[:20]))
            return
        answer = QMessageBox.question(
            self,
            "Confirm catalogue import",
            f"Validated {len(preview.rows)} rows from {preview.source_file_name}. Commit this import?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.import_csv(path)
        except CatalogueImportError as error:
            QMessageBox.warning(self, "Import failed", str(error))
            return
        self._load_filters()
        self._search()

    def _accept_selection(self) -> None:
        rows = self.results.selectionModel().selectedRows()
        if not rows:
            return
        self.selected = self.results.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self.accept()