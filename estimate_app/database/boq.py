from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal

from estimate_app.calculation.decimal_policy import (
    MeasurementType,
    MeasurementValues,
    QuantityTotals,
    calculate_amount,
    calculate_totals,
    decimal_from_text,
    decimal_to_text,
    signed_measurement_result,
)


UNVERIFIED_MANUAL_RATE = "Unverified manual rate"
UNVERIFIED_STATUS = "Unverified"


class UnitChangeRequiresResolution(ValueError):
    pass


@dataclass(frozen=True)
class BOQItem:
    id: int | None
    project_id: int
    serial_number: int
    work_section: str
    dsr_item_code: str
    description: str
    unit: str
    quantity_type: MeasurementType
    rate: Decimal | None = None
    rate_source: str = UNVERIFIED_MANUAL_RATE
    verification_status: str = UNVERIFIED_STATUS


@dataclass(frozen=True)
class Measurement:
    id: int | None
    boq_item_id: int
    particulars: str
    is_deduction: bool
    measurement_type: MeasurementType
    values: MeasurementValues
    remarks: str = ""


@dataclass(frozen=True)
class BOQSummary:
    totals: QuantityTotals | None
    amount: Decimal | None
    rate_missing: bool

    @property
    def incomplete(self) -> bool:
        return self.totals is None or self.rate_missing


class BOQRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_items(self, project_id: int) -> list[BOQItem]:
        rows = self.connection.execute(
            "SELECT * FROM boq_items WHERE project_id = ? ORDER BY serial_number",
            (project_id,),
        ).fetchall()
        return [self._item_from_row(row) for row in rows]

    def get_item(self, item_id: int) -> BOQItem | None:
        row = self.connection.execute(
            "SELECT * FROM boq_items WHERE id = ?", (item_id,)
        ).fetchone()
        return self._item_from_row(row) if row else None

    def save_item(
        self,
        item: BOQItem,
        *,
        resolve_unit_change: bool = False,
    ) -> BOQItem:
        existing = self.get_item(item.id) if item.id is not None else None
        if existing and existing.unit != item.unit and self.list_measurements(item.id):
            if not resolve_unit_change:
                raise UnitChangeRequiresResolution(
                    "This item has measurements. Resolve the unit change explicitly before saving."
                )
            self.connection.execute("DELETE FROM measurements WHERE boq_item_id = ?", (item.id,))
        values = (
            item.project_id,
            item.serial_number,
            item.work_section,
            item.dsr_item_code,
            item.description,
            item.unit,
            item.quantity_type.value,
            decimal_to_text(decimal_from_text(item.rate, "Rate")),
            item.rate_source,
            item.verification_status,
        )
        if item.id is None:
            cursor = self.connection.execute(
                """
                INSERT INTO boq_items (
                    project_id, serial_number, work_section, dsr_item_code,
                    description, unit, quantity_type, rate, rate_source,
                    verification_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            item_id = cursor.lastrowid
        else:
            self.connection.execute(
                """
                UPDATE boq_items
                SET project_id = ?, serial_number = ?, work_section = ?,
                    dsr_item_code = ?, description = ?, unit = ?,
                    quantity_type = ?, rate = ?, rate_source = ?,
                    verification_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                values + (item.id,),
            )
            item_id = item.id
        self.connection.commit()
        return self.get_item(item_id)  # type: ignore[arg-type]

    def delete_item(self, item_id: int) -> None:
        self.connection.execute("DELETE FROM boq_items WHERE id = ?", (item_id,))
        self.connection.commit()

    def reorder_items(self, project_id: int, ordered_ids: list[int]) -> None:
        current_ids = [item.id for item in self.list_items(project_id)]
        if sorted(current_ids) != sorted(ordered_ids):
            raise ValueError("The BOQ order does not contain exactly this project's items.")
        with self.connection:
            self.connection.execute(
                "UPDATE boq_items SET serial_number = -id WHERE project_id = ?",
                (project_id,),
            )
            self.connection.executemany(
                "UPDATE boq_items SET serial_number = ? WHERE id = ?",
                [(serial, item_id) for serial, item_id in enumerate(ordered_ids, 1)],
            )

    def list_measurements(self, item_id: int) -> list[Measurement]:
        rows = self.connection.execute(
            "SELECT * FROM measurements WHERE boq_item_id = ? ORDER BY id", (item_id,)
        ).fetchall()
        return [self._measurement_from_row(row) for row in rows]

    def save_measurement(self, measurement: Measurement) -> Measurement:
        values = self._measurement_values(measurement)
        if measurement.id is None:
            cursor = self.connection.execute(
                """
                INSERT INTO measurements (
                    boq_item_id, particulars, is_deduction, measurement_type,
                    repetitions, number, length, breadth, height_depth,
                    direct_quantity, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            measurement_id = cursor.lastrowid
        else:
            self.connection.execute(
                """
                UPDATE measurements
                SET boq_item_id = ?, particulars = ?, is_deduction = ?,
                    measurement_type = ?, repetitions = ?, number = ?,
                    length = ?, breadth = ?, height_depth = ?,
                    direct_quantity = ?, remarks = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                values + (measurement.id,),
            )
            measurement_id = measurement.id
        self.connection.commit()
        row = self.connection.execute(
            "SELECT * FROM measurements WHERE id = ?", (measurement_id,)
        ).fetchone()
        return self._measurement_from_row(row)

    def delete_measurement(self, measurement_id: int) -> None:
        self.connection.execute("DELETE FROM measurements WHERE id = ?", (measurement_id,))
        self.connection.commit()

    def summary(self, item_id: int) -> BOQSummary:
        item = self.get_item(item_id)
        if item is None:
            raise ValueError("BOQ item does not exist.")
        measurements = self.list_measurements(item_id)
        if not measurements:
            return BOQSummary(None, None, item.rate is None)
        results = [
            signed_measurement_result(
                measurement.measurement_type,
                measurement.values,
                measurement.is_deduction,
            )
            for measurement in measurements
        ]
        totals = calculate_totals(results)
        amount = calculate_amount(totals.displayed_quantity, item.rate) if item.rate is not None else None
        return BOQSummary(totals, amount, item.rate is None)

    @staticmethod
    def _measurement_values(measurement: Measurement) -> tuple[object, ...]:
        values = measurement.values
        parsed = [
            decimal_from_text(values.repetitions, "Repetitions"),
            decimal_from_text(values.number, "Number"),
            decimal_from_text(values.length, "Length"),
            decimal_from_text(values.breadth, "Breadth"),
            decimal_from_text(values.height_depth, "Height / depth"),
            decimal_from_text(values.direct_quantity, "Direct quantity"),
        ]
        return (
            measurement.boq_item_id,
            measurement.particulars,
            int(measurement.is_deduction),
            measurement.measurement_type.value,
            *(decimal_to_text(value) for value in parsed),
            measurement.remarks,
        )

    @staticmethod
    def _item_from_row(row: sqlite3.Row) -> BOQItem:
        return BOQItem(
            id=row["id"],
            project_id=row["project_id"],
            serial_number=row["serial_number"],
            work_section=row["work_section"],
            dsr_item_code=row["dsr_item_code"],
            description=row["description"],
            unit=row["unit"],
            quantity_type=MeasurementType(row["quantity_type"]),
            rate=decimal_from_text(row["rate"], "Rate"),
            rate_source=row["rate_source"],
            verification_status=row["verification_status"],
        )

    @staticmethod
    def _measurement_from_row(row: sqlite3.Row) -> Measurement:
        return Measurement(
            id=row["id"],
            boq_item_id=row["boq_item_id"],
            particulars=row["particulars"],
            is_deduction=bool(row["is_deduction"]),
            measurement_type=MeasurementType(row["measurement_type"]),
            values=MeasurementValues(
                repetitions=decimal_from_text(row["repetitions"], "Repetitions"),
                number=decimal_from_text(row["number"], "Number"),
                length=decimal_from_text(row["length"], "Length"),
                breadth=decimal_from_text(row["breadth"], "Breadth"),
                height_depth=decimal_from_text(row["height_depth"], "Height / depth"),
                direct_quantity=decimal_from_text(row["direct_quantity"], "Direct quantity"),
            ),
            remarks=row["remarks"],
        )