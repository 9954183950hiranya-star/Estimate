from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum


class MeasurementType(str, Enum):
    VOLUME = "volume"
    AREA = "area"
    LENGTH = "length"
    COUNT = "count"
    DIRECT = "direct"


MONEY_PLACES = Decimal("0.01")
QUANTITY_PLACES = Decimal("0.001")


def round_money(value: Decimal) -> Decimal:
    """Round monetary values to two decimal places using half-up rounding."""
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def round_quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)


def decimal_from_text(value: str | Decimal | None, field_name: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field_name} must be a decimal number.") from error
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite.")
    if parsed < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return parsed


def decimal_to_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError("Cannot store a non-finite decimal.")
    return format(value, "f")


@dataclass(frozen=True)
class MeasurementValues:
    repetitions: Decimal | None = None
    number: Decimal | None = None
    length: Decimal | None = None
    breadth: Decimal | None = None
    height_depth: Decimal | None = None
    direct_quantity: Decimal | None = None


@dataclass(frozen=True)
class MeasurementResult:
    quantity: Decimal
    addition: Decimal
    deduction: Decimal


@dataclass(frozen=True)
class QuantityTotals:
    gross_additions: Decimal
    gross_deductions: Decimal
    net_quantity: Decimal
    displayed_quantity: Decimal

    @property
    def has_negative_net(self) -> bool:
        return self.net_quantity < 0


def calculate_measurement(
    measurement_type: MeasurementType, values: MeasurementValues
) -> MeasurementResult:
    def required(value: Decimal | None, name: str) -> Decimal:
        if value is None:
            raise ValueError(f"{name} is required for {measurement_type.value} measurements.")
        return value

    if measurement_type is not MeasurementType.DIRECT:
        repetitions = required(values.repetitions, "Repetitions")
        number = required(values.number, "Number")
    if measurement_type is MeasurementType.VOLUME:
        quantity = repetitions * number * required(values.length, "Length")
        quantity *= required(values.breadth, "Breadth") * required(values.height_depth, "Height / depth")
    elif measurement_type is MeasurementType.AREA:
        quantity = repetitions * number * required(values.length, "Length")
        quantity *= required(values.breadth, "Breadth")
    elif measurement_type is MeasurementType.LENGTH:
        quantity = repetitions * number * required(values.length, "Length")
    elif measurement_type is MeasurementType.COUNT:
        quantity = repetitions * number
    elif measurement_type is MeasurementType.DIRECT:
        quantity = required(values.direct_quantity, "Direct quantity")
    else:
        raise ValueError(f"Unsupported measurement type: {measurement_type}")
    return MeasurementResult(quantity=quantity, addition=quantity, deduction=Decimal("0"))


def signed_measurement_result(
    measurement_type: MeasurementType, values: MeasurementValues, is_deduction: bool
) -> MeasurementResult:
    result = calculate_measurement(measurement_type, values)
    if is_deduction:
        return MeasurementResult(result.quantity, Decimal("0"), result.quantity)
    return result


def calculate_totals(results: list[MeasurementResult]) -> QuantityTotals:
    additions = sum((result.addition for result in results), Decimal("0"))
    deductions = sum((result.deduction for result in results), Decimal("0"))
    net = additions - deductions
    return QuantityTotals(
        gross_additions=additions,
        gross_deductions=deductions,
        net_quantity=net,
        displayed_quantity=round_quantity(net),
    )


def calculate_amount(quantity: Decimal, rate: Decimal) -> Decimal:
    return round_money(round_quantity(quantity) * rate)
