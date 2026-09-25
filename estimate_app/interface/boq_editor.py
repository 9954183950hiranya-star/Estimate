from __future__ import annotations

import sqlite3
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from estimate_app.calculation.decimal_policy import (
    MeasurementType,
    MeasurementValues,
    decimal_from_text,
    round_money,
    round_quantity,
)
from estimate_app.database.boq import (
    BOQItem,
    BOQRepository,
    Measurement,
    UNVERIFIED_MANUAL_RATE,
    UNVERIFIED_STATUS,
)
from estimate_app.database.catalogue import (
    MANUAL_OVERRIDE,
    CatalogueRepository,
)
from estimate_app.interface.catalogue_dialog import CatalogueDialog


TYPE_LABELS = {
    MeasurementType.VOLUME: "Volume",
    MeasurementType.AREA: "Area",
    MeasurementType.LENGTH: "Length",
    MeasurementType.COUNT: "Count",
    MeasurementType.DIRECT: "Direct quantity",
}


class BOQEditor(QWidget):
    def __init__(self, repository: BOQRepository, catalogue_repository: CatalogueRepository) -> None:
        super().__init__()
        self.repository = repository
        self.catalogue_repository = catalogue_repository
        self.current_project_id: int | None = None
        self.current_item_id: int | None = None
        self.current_cutoff_date: str | None = None
        self.selected_catalogue_id: int | None = None
        self.selected_catalogue_version_id: int | None = None
        self.selected_catalogue_rate: Decimal | None = None
        self._build_ui()
        self._set_enabled(False)

    def _build_ui(self) -> None:
        self.item_table = QTableWidget(0, 9)
        self.item_table.setHorizontalHeaderLabels(
            ["S. No.", "Section", "DSR item code", "Description", "Unit", "Quantity", "Rate", "Amount", "Status"]
        )
        self.item_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.item_table.itemSelectionChanged.connect(self._item_selected)

        self.new_item_button = QPushButton("New BOQ Item")
        self.save_item_button = QPushButton("Save BOQ Item")
        self.delete_item_button = QPushButton("Delete Item")
        self.up_button = QPushButton("Move Up")
        self.down_button = QPushButton("Move Down")
        self.select_catalogue_button = QPushButton("Select verified DSR item")
        self.review_updates_button = QPushButton("Review rate updates")
        self.new_item_button.clicked.connect(self._new_item)
        self.save_item_button.clicked.connect(self._save_item)
        self.delete_item_button.clicked.connect(self._delete_item)
        self.up_button.clicked.connect(lambda: self._move_item(-1))
        self.down_button.clicked.connect(lambda: self._move_item(1))
        self.select_catalogue_button.clicked.connect(self._select_catalogue)
        self.review_updates_button.clicked.connect(self._review_rate_updates)
        item_buttons = QHBoxLayout()
        for button in (self.new_item_button, self.save_item_button, self.delete_item_button, self.up_button, self.down_button, self.select_catalogue_button, self.review_updates_button):
            item_buttons.addWidget(button)

        self.work_section = QLineEdit()
        self.dsr_item_code = QLineEdit()
        self.description = QLineEdit()
        self.unit = QLineEdit()
        self.unit.textChanged.connect(self._apply_quantity_type_policy)
        self.quantity_type = QComboBox()
        for measurement_type in MeasurementType:
            self.quantity_type.addItem(TYPE_LABELS[measurement_type], measurement_type)
        self.rate = QLineEdit()
        self.rate_source = QLineEdit(UNVERIFIED_MANUAL_RATE)
        self.rate_source.setReadOnly(True)
        self.verification_status = QLabel(UNVERIFIED_STATUS)
        item_form = QFormLayout()
        item_form.addRow("Work section", self.work_section)
        item_form.addRow("DSR item code", self.dsr_item_code)
        item_form.addRow("Full description", self.description)
        item_form.addRow("Unit", self.unit)
        item_form.addRow("Quantity type", self.quantity_type)
        item_form.addRow("Rate (₹)", self.rate)
        item_form.addRow("Rate source", self.rate_source)
        item_form.addRow("Verification status", self.verification_status)
        item_group = QGroupBox("BOQ item")
        item_group.setLayout(item_form)

        self.measurement_table = QTableWidget(0, 12)
        self.measurement_table.setHorizontalHeaderLabels(
            ["Particulars / location", "+/-", "Type", "Repetitions", "Number", "Length", "Breadth", "Height / depth", "Direct quantity", "Quantity", "Remarks", "ID"]
        )
        self.measurement_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.measurement_table.itemSelectionChanged.connect(self._measurement_selected)
        self.measurement_type = QComboBox()
        for measurement_type in MeasurementType:
            self.measurement_type.addItem(TYPE_LABELS[measurement_type], measurement_type)
        self.particulars = QLineEdit()
        self.is_deduction = QCheckBox("Deduction")
        self.repetitions = QLineEdit()
        self.number = QLineEdit()
        self.length = QLineEdit()
        self.breadth = QLineEdit()
        self.height_depth = QLineEdit()
        self.direct_quantity = QLineEdit()
        self.remarks = QLineEdit()
        self.measurement_quantity = QLabel("0.000")
        measurement_form = QFormLayout()
        measurement_form.addRow("Particulars / location", self.particulars)
        measurement_form.addRow("Measurement type", self.measurement_type)
        measurement_form.addRow("Addition or deduction", self.is_deduction)
        measurement_form.addRow("Repetitions", self.repetitions)
        measurement_form.addRow("Number", self.number)
        measurement_form.addRow("Length (m)", self.length)
        measurement_form.addRow("Breadth (m)", self.breadth)
        measurement_form.addRow("Height / depth (m)", self.height_depth)
        measurement_form.addRow("Direct quantity", self.direct_quantity)
        measurement_form.addRow("Remarks", self.remarks)
        measurement_form.addRow("Calculated quantity", self.measurement_quantity)
        self.save_measurement_button = QPushButton("Save Measurement")
        self.new_measurement_button = QPushButton("New Measurement")
        self.delete_measurement_button = QPushButton("Delete Measurement")
        self.save_measurement_button.clicked.connect(self._save_measurement)
        self.new_measurement_button.clicked.connect(self._new_measurement)
        self.delete_measurement_button.clicked.connect(self._delete_measurement)
        measurement_buttons = QHBoxLayout()
        for button in (self.new_measurement_button, self.save_measurement_button, self.delete_measurement_button):
            measurement_buttons.addWidget(button)
        measurement_form.addRow(measurement_buttons)
        measurement_group = QGroupBox("Detailed measurements")
        measurement_layout = QVBoxLayout()
        measurement_layout.addWidget(self.measurement_table)
        measurement_layout.addLayout(measurement_form)
        measurement_group.setLayout(measurement_layout)

        self.summary_label = QLabel("Measurements required")
        layout = QVBoxLayout(self)
        layout.addLayout(item_buttons)
        layout.addWidget(self.item_table)
        layout.addWidget(item_group)
        layout.addWidget(measurement_group)
        layout.addWidget(self.summary_label)
        for field in (self.repetitions, self.number, self.length, self.breadth, self.height_depth, self.direct_quantity, self.measurement_type, self.is_deduction):
            if hasattr(field, "textChanged"):
                field.textChanged.connect(self._preview_measurement)
            elif hasattr(field, "currentIndexChanged"):
                field.currentIndexChanged.connect(self._preview_measurement)
            else:
                field.stateChanged.connect(self._preview_measurement)
        self._update_dimension_inputs()

    def set_project(self, project_id: int | None, cutoff_date: str | None = None) -> None:
        self.current_project_id = project_id
        self.current_cutoff_date = cutoff_date
        self.current_item_id = None
        self._set_enabled(project_id is not None)
        self._load_items()
        self._new_item()

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (self.item_table, self.new_item_button, self.save_item_button, self.delete_item_button, self.up_button, self.down_button, self.select_catalogue_button, self.review_updates_button, self.measurement_table, self.new_measurement_button, self.save_measurement_button, self.delete_measurement_button):
            widget.setEnabled(enabled)

    def _load_items(self) -> None:
        self.item_table.setRowCount(0)
        if self.current_project_id is None:
            return
        for item in self.repository.list_items(self.current_project_id):
            self._add_item_row(item)

    def _add_item_row(self, item: BOQItem) -> None:
        row = self.item_table.rowCount()
        self.item_table.insertRow(row)
        summary = self.repository.summary(item.id) if item.id is not None else None
        quantity = "Measurements required" if summary is None or summary.totals is None else f"{summary.totals.displayed_quantity:.3f}"
        amount = "" if summary is None or summary.amount is None else f"₹{summary.amount:.2f}"
        status = "Needs catalogue review" if item.needs_catalogue_review else item.verification_status
        values = [str(item.serial_number), item.work_section, item.dsr_item_code, item.description, item.unit, quantity, "" if item.rate is None else f"₹{item.rate:.2f}", amount, status]
        for column, value in enumerate(values):
            self.item_table.setItem(row, column, QTableWidgetItem(value))
        self.item_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.id)

    def _item_selected(self) -> None:
        rows = self.item_table.selectionModel().selectedRows()
        if not rows:
            return
        item_id = self.item_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        item = self.repository.get_item(item_id)
        if item is None:
            return
        self.current_item_id = item.id
        self.work_section.setText(item.work_section)
        self.dsr_item_code.setText(item.dsr_item_code)
        self.description.setText(item.description)
        self.unit.setText(item.unit)
        self.quantity_type.setCurrentIndex(self.quantity_type.findData(item.quantity_type))
        self._apply_quantity_type_policy()
        self.rate.setText("" if item.rate is None else format(item.rate, "f"))
        self.rate_source.setText(item.rate_source)
        self.verification_status.setText(item.verification_status)
        self.selected_catalogue_id = item.catalogue_item_id
        self.selected_catalogue_version_id = item.catalogue_version_id
        self.selected_catalogue_rate = item.rate if item.catalogue_item_id is not None else None
        self._load_measurements()

    def _new_item(self) -> None:
        self.current_item_id = None
        for field in (self.work_section, self.dsr_item_code, self.description, self.unit, self.rate):
            field.clear()
        self.rate_source.setText(UNVERIFIED_MANUAL_RATE)
        self.verification_status.setText(UNVERIFIED_STATUS)
        self.selected_catalogue_id = None
        self.selected_catalogue_version_id = None
        self.selected_catalogue_rate = None
        self.item_table.clearSelection()
        self._clear_measurement_form()
        self._load_measurements()
        self._update_summary()

    def _save_item(self) -> None:
        if self.current_project_id is None:
            return
        required = {
            "Work section": self.work_section.text().strip(),
            "DSR item code": self.dsr_item_code.text().strip(),
            "Full description": self.description.text().strip(),
            "Unit": self.unit.text().strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            QMessageBox.warning(self, "Incomplete BOQ item", "Enter: " + ", ".join(missing))
            return
        try:
            rate = decimal_from_text(self.rate.text().strip(), "Rate")
        except ValueError as error:
            QMessageBox.warning(self, "Invalid rate", str(error))
            return
        resolve_unit_change = False
        existing = self.repository.get_item(self.current_item_id) if self.current_item_id else None
        catalogue_item_id = existing.catalogue_item_id if existing else self.selected_catalogue_id
        catalogue_version_id = existing.catalogue_version_id if existing else self.selected_catalogue_version_id
        manual_override_reason = existing.manual_override_reason if existing else None
        verification_status = self.verification_status.text()
        rate_source = self.rate_source.text()
        original_catalogue_rate = existing.rate if existing and existing.catalogue_item_id is not None else self.selected_catalogue_rate
        if original_catalogue_rate is not None and rate != original_catalogue_rate:
            reason, accepted = QInputDialog.getText(self, "Manual override reason", "Why is the verified DSR rate being changed?")
            if not accepted or not reason.strip():
                QMessageBox.warning(self, "Manual override reason required", "A reason is required for a manual rate override.")
                return
            verification_status = MANUAL_OVERRIDE
            rate_source = MANUAL_OVERRIDE
            manual_override_reason = reason.strip()
        if existing and existing.unit != self.unit.text().strip() and self.repository.list_measurements(existing.id):
            answer = QMessageBox.question(self, "Resolve unit change", "Changing the unit will delete existing measurements. Continue?")
            if answer != QMessageBox.StandardButton.Yes:
                return
            resolve_unit_change = True
        try:
            item = self.repository.save_item(
                BOQItem(
                    self.current_item_id,
                    self.current_project_id,
                    existing.serial_number if existing else len(self.repository.list_items(self.current_project_id)) + 1,
                    required["Work section"],
                    required["DSR item code"],
                    required["Full description"],
                    required["Unit"],
                    self._current_type(self.quantity_type),
                    rate,
                    rate_source,
                    verification_status,
                    catalogue_item_id,
                    catalogue_version_id,
                    manual_override_reason,
                ),
                resolve_unit_change=resolve_unit_change,
            )
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Could not save BOQ item", str(error))
            return
        self.current_item_id = item.id
        self._load_items()
        self._select_item(item.id)

    def _select_catalogue(self) -> None:
        dialog = CatalogueDialog(self.catalogue_repository, self.current_cutoff_date, self)
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.selected is None:
            return
        resolved = dialog.selected
        item = resolved.item
        self.current_item_id = self.current_item_id
        self.work_section.setText(item.chapter)
        self.dsr_item_code.setText(item.item_code)
        self.description.setText(item.description)
        self.unit.setText(item.canonical_unit)
        self.quantity_type.setCurrentIndex(self.quantity_type.findData(self._quantity_type_for_unit(item.canonical_unit)))
        self._apply_quantity_type_policy()
        self.rate.setText(format(item.rate, "f") if item.rate is not None else "")
        self.rate_source.setText(f"{item.source_document_name}, p. {item.source_page}")
        self.verification_status.setText(item.verification_status)
        self.selected_catalogue_id = item.id
        self.selected_catalogue_version_id = resolved.applied_corrections[-1].id if resolved.applied_corrections else item.id
        self.selected_catalogue_rate = item.rate

    def _review_rate_updates(self) -> None:
        if self.current_item_id is None:
            QMessageBox.information(self, "Rate updates", "Save or select a BOQ item first.")
            return
        item = self.repository.get_item(self.current_item_id)
        if item is None or item.catalogue_item_id is None:
            QMessageBox.information(self, "Rate updates", "This item has no catalogue snapshot to review.")
            return
        catalogue = self.catalogue_repository.get_item(item.catalogue_item_id)
        if catalogue is None:
            QMessageBox.warning(self, "Rate updates", "The original catalogue record is unavailable.")
            return
        resolved = self.catalogue_repository.resolve_item(catalogue.schedule_name, catalogue.edition, catalogue.item_code, self.current_cutoff_date)
        changed = resolved.deleted or any((resolved.item.description, resolved.item.canonical_unit, resolved.item.rate) != (item.description, item.unit, item.rate))
        if not changed:
            QMessageBox.information(self, "Rate updates", "No applicable verified rate update was found.")
            return
        details = "The catalogue differs from this BOQ snapshot. Apply the reviewed update?"
        if resolved.deleted:
            details = "The catalogue item is deleted by an applicable correction. Do not apply this update automatically."
        if resolved.deleted or QMessageBox.question(self, "Review rate updates", details) != QMessageBox.StandardButton.Yes:
            return
        self.description.setText(resolved.item.description)
        self.unit.setText(resolved.item.canonical_unit)
        self.rate.setText(format(resolved.item.rate, "f") if resolved.item.rate is not None else "")
        self.rate_source.setText(f"{resolved.item.source_document_name}, p. {resolved.item.source_page}")
        self.selected_catalogue_rate = resolved.item.rate
        self.selected_catalogue_version_id = resolved.applied_corrections[-1].id if resolved.applied_corrections else resolved.item.id
        self._save_item()

    @staticmethod
    def _quantity_type_for_unit(unit: str):
        lowered = unit.lower()
        if lowered in {"cum", "m3", "m³"}:
            return MeasurementType.VOLUME
        if lowered in {"sqm", "m2", "m²"}:
            return MeasurementType.AREA
        if lowered in {"m", "rm"}:
            return MeasurementType.LENGTH
        if lowered in {"each", "no", "nos"}:
            return MeasurementType.COUNT
        return MeasurementType.DIRECT

    def _apply_quantity_type_policy(self) -> None:
        unsupported_compound_unit = self.unit.text().strip().lower() == "cm per metre"
        for index in range(self.quantity_type.count()):
            item = self.quantity_type.model().item(index)
            measurement_type = self.quantity_type.itemData(index)
            item.setEnabled(not unsupported_compound_unit or measurement_type == MeasurementType.DIRECT.value)
        if unsupported_compound_unit:
            self.quantity_type.setCurrentIndex(self.quantity_type.findData(MeasurementType.DIRECT))

    def _delete_item(self) -> None:
        if self.current_item_id is None:
            return
        has_measurements = bool(self.repository.list_measurements(self.current_item_id))
        if has_measurements:
            answer = QMessageBox.question(self, "Delete BOQ item", "This item contains measurements. Delete the item and all its measurements?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.repository.delete_item(self.current_item_id)
        self._load_items()
        self._new_item()

    def _move_item(self, direction: int) -> None:
        if self.current_project_id is None or self.current_item_id is None:
            return
        ids = [item.id for item in self.repository.list_items(self.current_project_id)]
        index = ids.index(self.current_item_id)
        target = index + direction
        if target < 0 or target >= len(ids):
            return
        ids[index], ids[target] = ids[target], ids[index]
        self.repository.reorder_items(self.current_project_id, ids)
        self._load_items()
        self._select_item(self.current_item_id)

    def _select_item(self, item_id: int | None) -> None:
        for row in range(self.item_table.rowCount()):
            if self.item_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == item_id:
                self.item_table.selectRow(row)
                return

    def _load_measurements(self) -> None:
        self.measurement_table.setRowCount(0)
        if self.current_item_id is None:
            return
        for measurement in self.repository.list_measurements(self.current_item_id):
            row = self.measurement_table.rowCount()
            self.measurement_table.insertRow(row)
            result = self.repository.summary(self.current_item_id)
            quantity = self._measurement_quantity(measurement)
            values = [measurement.particulars, "-" if measurement.is_deduction else "+", TYPE_LABELS[measurement.measurement_type], *(self._display_value(value) for value in (measurement.values.repetitions, measurement.values.number, measurement.values.length, measurement.values.breadth, measurement.values.height_depth, measurement.values.direct_quantity)), f"{quantity:.3f}", measurement.remarks, str(measurement.id)]
            for column, value in enumerate(values):
                self.measurement_table.setItem(row, column, QTableWidgetItem(value))
            self.measurement_table.item(row, 11).setData(Qt.ItemDataRole.UserRole, measurement.id)
        self._update_summary()

    def _measurement_selected(self) -> None:
        rows = self.measurement_table.selectionModel().selectedRows()
        if not rows:
            return
        measurement_id = self.measurement_table.item(rows[0].row(), 11).data(Qt.ItemDataRole.UserRole)
        measurement = next((item for item in self.repository.list_measurements(self.current_item_id) if item.id == measurement_id), None)
        if measurement is None:
            return
        self._load_measurement_form(measurement)

    def _load_measurement_form(self, measurement: Measurement) -> None:
        self.particulars.setText(measurement.particulars)
        self.measurement_type.setCurrentIndex(self.measurement_type.findData(measurement.measurement_type))
        self.is_deduction.setChecked(measurement.is_deduction)
        fields = (self.repetitions, self.number, self.length, self.breadth, self.height_depth, self.direct_quantity)
        for field, value in zip(fields, (measurement.values.repetitions, measurement.values.number, measurement.values.length, measurement.values.breadth, measurement.values.height_depth, measurement.values.direct_quantity)):
            field.setText(self._display_value(value, empty=True))
        self.remarks.setText(measurement.remarks)
        self.measurement_quantity.setText(f"{self._measurement_quantity(measurement):.3f}")
        self.new_measurement_button.setProperty("measurement_id", measurement.id)
        self._update_dimension_inputs()

    def _new_measurement(self) -> None:
        self.new_measurement_button.setProperty("measurement_id", None)
        self._clear_measurement_form()

    def _clear_measurement_form(self) -> None:
        self.particulars.clear()
        self.is_deduction.setChecked(False)
        for field in (self.repetitions, self.number, self.length, self.breadth, self.height_depth, self.direct_quantity, self.remarks):
            field.clear()
        self.measurement_quantity.setText("0.000")
        self._update_dimension_inputs()

    def _save_measurement(self) -> None:
        if self.current_item_id is None:
            return
        try:
            values = MeasurementValues(
                decimal_from_text(self.repetitions.text().strip(), "Repetitions"),
                decimal_from_text(self.number.text().strip(), "Number"),
                decimal_from_text(self.length.text().strip(), "Length"),
                decimal_from_text(self.breadth.text().strip(), "Breadth"),
                decimal_from_text(self.height_depth.text().strip(), "Height / depth"),
                decimal_from_text(self.direct_quantity.text().strip(), "Direct quantity"),
            )
            measurement = Measurement(
                self.new_measurement_button.property("measurement_id"),
                self.current_item_id,
                self.particulars.text().strip(),
                self.is_deduction.isChecked(),
                self._current_type(self.measurement_type),
                values,
                self.remarks.text(),
            )
            self.repository.save_measurement(measurement)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self, "Invalid measurement", str(error))
            return
        self._load_measurements()
        self._new_measurement()
        self._load_items()
        self._select_item(self.current_item_id)

    def _delete_measurement(self) -> None:
        measurement_id = self.new_measurement_button.property("measurement_id")
        if measurement_id is None:
            return
        self.repository.delete_measurement(measurement_id)
        self._load_measurements()
        self._new_measurement()
        self._load_items()
        self._select_item(self.current_item_id)

    def _preview_measurement(self) -> None:
        try:
            values = MeasurementValues(*(decimal_from_text(field.text().strip(), field.objectName() or "Value") for field in (self.repetitions, self.number, self.length, self.breadth, self.height_depth, self.direct_quantity)))
            measurement = Measurement(None, 0, "", self.is_deduction.isChecked(), self._current_type(self.measurement_type), values)
            self.measurement_quantity.setText(f"{self._measurement_quantity(measurement):.3f}")
        except ValueError:
            self.measurement_quantity.setText("Invalid")

    def _update_dimension_inputs(self) -> None:
        measurement_type = self._current_type(self.measurement_type)
        active = {
            self.repetitions: measurement_type is not MeasurementType.DIRECT,
            self.number: measurement_type is not MeasurementType.DIRECT,
            self.length: measurement_type in (MeasurementType.VOLUME, MeasurementType.AREA, MeasurementType.LENGTH),
            self.breadth: measurement_type in (MeasurementType.VOLUME, MeasurementType.AREA),
            self.height_depth: measurement_type is MeasurementType.VOLUME,
            self.direct_quantity: measurement_type is MeasurementType.DIRECT,
        }
        for field, enabled in active.items():
            field.setEnabled(enabled)
        self._preview_measurement()

    def _measurement_quantity(self, measurement: Measurement) -> Decimal:
        from estimate_app.calculation.decimal_policy import signed_measurement_result

        return signed_measurement_result(measurement.measurement_type, measurement.values, measurement.is_deduction).quantity

    @staticmethod
    def _current_type(combo: QComboBox) -> MeasurementType:
        return MeasurementType(combo.currentData())

    @staticmethod
    def _display_value(value: Decimal | None, empty: bool = False) -> str:
        if value is None:
            return "" if empty else ""
        return format(value, "f")

    def _update_summary(self) -> None:
        if self.current_item_id is None:
            self.summary_label.setText("Measurements required")
            return
        summary = self.repository.summary(self.current_item_id)
        if summary.totals is None:
            self.summary_label.setText("Measurements required")
            return
        status = "Negative net quantity" if summary.totals.has_negative_net else "Complete" if not summary.incomplete else "Incomplete: rate required"
        amount = "" if summary.amount is None else f" | Amount ₹{summary.amount:.2f}"
        self.summary_label.setText(f"Additions {summary.totals.gross_additions:.3f} | Deductions {summary.totals.gross_deductions:.3f} | Net {summary.totals.displayed_quantity:.3f} | {status}{amount}")