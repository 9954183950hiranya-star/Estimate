from __future__ import annotations

import sqlite3
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from estimate_app.database.catalogue import (
    CORRECTION_HEADERS,
    CatalogueImportError,
    CatalogueRepository,
    CorrectionSlip,
    ConflictingCorrectionsError,
    WITHDRAWN,
    blank_correction_template,
)
from estimate_app.calculation.decimal_policy import decimal_from_text


def _ask_reviewer(parent, title: str) -> tuple[str, str] | None:
    reviewer, accepted = QInputDialog.getText(parent, title, "Reviewer name:")
    if not accepted or not reviewer.strip():
        return None
    event_date, accepted = QInputDialog.getText(parent, title, "Date (YYYY-MM-DD):")
    if not accepted or not event_date.strip():
        return None
    return reviewer.strip(), event_date.strip()


class CatalogueReviewDialog(QDialog):
    def __init__(self, repository: CatalogueRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("CPWD DSR catalogue review")
        self.resize(1250, 700)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search code or description")
        self.status = QComboBox()
        self.status.addItems(["All", "Unverified", "Verified", "Withdrawn"])
        self.search.textChanged.connect(self._refresh)
        self.status.currentTextChanged.connect(self._refresh)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search"))
        filters.addWidget(self.search)
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self.status)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["Code", "Parent", "Description", "Original unit", "Canonical unit", "Rate", "Volume", "Source page", "Status", "Reviewer / date"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.source_label = QLabel("Select a record to review its source.")
        verify_button = QPushButton("Verify selected")
        verify_button.clicked.connect(self._verify)
        withdraw_button = QPushButton("Withdraw verification")
        withdraw_button.clicked.connect(self._withdraw)
        attach_button = QPushButton("Attach local PDF")
        attach_button.clicked.connect(self._attach_pdf)
        open_button = QPushButton("Open source PDF")
        open_button.clicked.connect(self._open_pdf)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        buttons = QDialogButtonBox()
        for button in (verify_button, withdraw_button, attach_button, open_button):
            buttons.addButton(button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(close_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.table)
        layout.addWidget(self.source_label)
        layout.addWidget(buttons)

    def _refresh(self) -> None:
        status = "" if self.status.currentText() == "All" else self.status.currentText()
        items = self.repository.list_review_items(status)
        query = self.search.text().strip().lower()
        items = [item for item in items if not query or query in item.item_code.lower() or query in item.description.lower()]
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            reviewer = "" if not item.reviewer else f"{item.reviewer} / {item.verification_date or ''}"
            rate = "" if item.rate is None else f"₹{item.rate:.2f}"
            values = [item.item_code, item.parent_item_code or "", item.description, item.original_unit, item.canonical_unit, rate, item.volume, f"{item.source_document_name}, p. {item.source_page}", item.verification_status, reviewer]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.id)

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def _selection_changed(self) -> None:
        item_id = self._selected_id()
        item = self.repository.get_item(item_id) if item_id else None
        self.source_label.setText("Select a record to review its source." if item is None else f"Source: {item.source_document_name}, page {item.source_page}")

    def _verify(self) -> None:
        item_id = self._selected_id()
        reviewer = _ask_reviewer(self, "Verify catalogue item") if item_id else None
        if item_id is None or reviewer is None:
            return
        try:
            self.repository.verify_item(item_id, *reviewer)
        except ValueError as error:
            QMessageBox.warning(self, "Verification failed", str(error))
            return
        self._refresh()

    def _withdraw(self) -> None:
        item_id = self._selected_id()
        if item_id is None:
            return
        reviewer = _ask_reviewer(self, "Withdraw catalogue verification")
        if reviewer is None:
            return
        reason, accepted = QInputDialog.getText(self, "Withdrawal reason", "Reason:")
        if not accepted or not reason.strip():
            return
        try:
            self.repository.withdraw_item(item_id, reviewer[0], reviewer[1], reason)
        except ValueError as error:
            QMessageBox.warning(self, "Withdrawal failed", str(error))
            return
        self._refresh()

    def _attach_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach local PDF", "", "PDF files (*.pdf)")
        if not path:
            return
        try:
            document = self.repository.attach_reference_document(path)
            self.source_label.setText(f"Attached {document['document_name']} with checksum {document['source_checksum']}")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "PDF attachment failed", str(error))

    def _open_pdf(self) -> None:
        item_id = self._selected_id()
        item = self.repository.get_item(item_id) if item_id else None
        if item is None:
            return
        try:
            self.repository.open_reference_document_by_name(item.source_document_name)
        except (OSError, FileNotFoundError) as error:
            QMessageBox.warning(self, "Reference PDF unavailable", str(error))


class CorrectionReviewDialog(QDialog):
    def __init__(self, repository: CatalogueRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.current_id: int | None = None
        self.setWindowTitle("Correction-slip review")
        self.resize(1250, 760)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Slip", "Item code", "Operation", "Publication", "Effective", "Source", "Status", "Reviewer"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._load_selected)
        self.slip_reference = QLineEdit()
        self.publication_date = QLineEdit()
        self.effective_date = QLineEdit()
        self.effective_date_source = QLineEdit()
        self.item_code = QLineEdit()
        self.operation = QComboBox()
        self.operation.addItems(["add", "amend", "delete"])
        self.source_document = QLineEdit()
        self.source_page = QLineEdit()
        self.changed_description = QLineEdit()
        self.changed_unit = QLineEdit()
        self.changed_rate = QLineEdit()
        self.changed_volume = QLineEdit()
        self.changed_chapter = QLineEdit()
        self.original_label = QLabel("Original item: select or enter an item code")
        self.proposed_label = QLabel("Proposed item: enter changed fields")
        form = QFormLayout()
        for label, field in (("Slip reference", self.slip_reference), ("Publication date", self.publication_date), ("Effective date", self.effective_date), ("Effective-date source", self.effective_date_source), ("Affected item code", self.item_code), ("Operation", self.operation), ("Source document", self.source_document), ("Source page", self.source_page), ("Changed description", self.changed_description), ("Changed canonical unit", self.changed_unit), ("Changed rate", self.changed_rate), ("Changed volume", self.changed_volume), ("Changed chapter", self.changed_chapter)):
            form.addRow(label, field)
        self.item_code.textChanged.connect(self._show_comparison)
        self.changed_description.textChanged.connect(self._show_comparison)
        self.changed_unit.textChanged.connect(self._show_comparison)
        self.changed_rate.textChanged.connect(self._show_comparison)
        self.conflict_label = QLabel()
        new_button = QPushButton("New draft")
        new_button.clicked.connect(self._new_draft)
        save_button = QPushButton("Save draft revision")
        save_button.clicked.connect(self._save_draft)
        verify_button = QPushButton("Verify selected")
        verify_button.clicked.connect(self._verify)
        withdraw_button = QPushButton("Withdraw verification")
        withdraw_button.clicked.connect(self._withdraw)
        import_button = QPushButton("Preview/import CSV")
        import_button.clicked.connect(self._import_csv)
        attach_button = QPushButton("Attach local PDF")
        attach_button.clicked.connect(self._attach_pdf)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        for button in (new_button, save_button, verify_button, withdraw_button, import_button, attach_button, close_button):
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.original_label)
        layout.addWidget(self.proposed_label)
        layout.addWidget(self.conflict_label)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def _refresh(self) -> None:
        corrections = self.repository.list_corrections()
        self.table.setRowCount(0)
        for correction in corrections:
            row = self.table.rowCount()
            self.table.insertRow(row)
            source = f"{correction.source_document_name}, p. {correction.source_page}"
            values = [correction.slip_reference, correction.item_code, correction.operation, correction.publication_date, correction.effective_date, source, correction.verification_status, correction.reviewer or ""]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, correction.id)

    def _load_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        self.current_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        correction = next(item for item in self.repository.list_corrections() if item.id == self.current_id)
        self.slip_reference.setText(correction.slip_reference)
        self.publication_date.setText(correction.publication_date)
        self.effective_date.setText(correction.effective_date)
        self.effective_date_source.setText(correction.effective_date_source)
        self.item_code.setText(correction.item_code)
        self.operation.setCurrentText(correction.operation)
        self.source_document.setText(correction.source_document_name)
        self.source_page.setText(str(correction.source_page))
        self.changed_description.setText(correction.changed_description or "")
        self.changed_unit.setText(correction.changed_canonical_unit or "")
        self.changed_rate.setText("" if correction.changed_rate is None else format(correction.changed_rate, "f"))
        self.changed_volume.setText(correction.changed_volume or "")
        self.changed_chapter.setText(correction.changed_chapter or "")
        self._show_comparison()

    def _show_comparison(self) -> None:
        code = self.item_code.text().strip()
        original = next((item for item in self.repository.list_items() if item.item_code == code), None)
        self.original_label.setText("Original item: " + ("not found" if original is None else f"{original.description} | {original.original_unit} | rate {original.rate}"))
        proposed = self.changed_description.text().strip() or (original.description if original else "")
        unit = self.changed_unit.text().strip() or (original.canonical_unit if original else "")
        rate = self.changed_rate.text().strip() or (str(original.rate) if original and original.rate is not None else "")
        self.proposed_label.setText(f"Proposed item: {proposed} | {unit} | rate {rate}")
        try:
            self.repository.resolve_item("CPWD DSR Civil", "2023", code, None) if code else None
            self.conflict_label.setText("")
        except (ConflictingCorrectionsError, ValueError) as error:
            self.conflict_label.setText(f"Conflict: {error}")

    def _new_draft(self) -> None:
        self.current_id = None
        for field in (self.slip_reference, self.publication_date, self.effective_date, self.effective_date_source, self.item_code, self.source_document, self.source_page, self.changed_description, self.changed_unit, self.changed_rate, self.changed_volume, self.changed_chapter):
            field.clear()
        self._show_comparison()

    def _form_value(self) -> CorrectionSlip:
        source_page = int(self.source_page.text().strip())
        return CorrectionSlip(None, self.slip_reference.text().strip(), self.publication_date.text().strip(), self.effective_date.text().strip(), self.effective_date_source.text().strip(), self.item_code.text().strip(), self.operation.currentText(), self.source_document.text().strip(), source_page, changed_description=self.changed_description.text().strip() or None, changed_canonical_unit=self.changed_unit.text().strip() or None, changed_rate=decimal_from_text(self.changed_rate.text().strip(), "changed rate"), changed_volume=self.changed_volume.text().strip() or None, changed_chapter=self.changed_chapter.text().strip() or None)

    def _save_draft(self) -> None:
        try:
            correction = self._form_value()
            created = self.repository.revise_correction(self.current_id, correction) if self.current_id else self.repository.add_correction(correction)
            self.current_id = created.id
            self._refresh()
        except (ValueError, TypeError, OSError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Draft not saved", str(error))

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def _verify(self) -> None:
        correction_id = self._selected_id()
        reviewer = _ask_reviewer(self, "Verify correction slip") if correction_id else None
        if correction_id is None or reviewer is None:
            return
        try:
            self.repository.verify_correction(correction_id, *reviewer)
        except ValueError as error:
            QMessageBox.warning(self, "Verification failed", str(error))
            return
        self._refresh()

    def _withdraw(self) -> None:
        correction_id = self._selected_id()
        reviewer = _ask_reviewer(self, "Withdraw correction verification") if correction_id else None
        if correction_id is None or reviewer is None:
            return
        reason, accepted = QInputDialog.getText(self, "Withdrawal reason", "Reason:")
        if not accepted or not reason.strip():
            return
        try:
            self.repository.withdraw_correction(correction_id, reviewer[0], reviewer[1], reason)
        except ValueError as error:
            QMessageBox.warning(self, "Withdrawal failed", str(error))
            return
        self._refresh()

    def _import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import correction CSV", "", "CSV files (*.csv)")
        if not path:
            return
        preview = self.repository.preview_correction_csv(path)
        if preview.errors:
            QMessageBox.warning(self, "Correction import validation failed", "\n".join(preview.errors[:20]))
            return
        if QMessageBox.question(self, "Confirm correction import", f"Validated {len(preview.rows)} rows. Commit import?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.import_correction_csv(path)
        except CatalogueImportError as error:
            QMessageBox.warning(self, "Correction import failed", str(error))
            return
        self._refresh()

    def _attach_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach local PDF", "", "PDF files (*.pdf)")
        if path:
            try:
                self.repository.attach_reference_document(path)
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "PDF attachment failed", str(error))