from decimal import Decimal

import pytest

from estimate_app.calculation.decimal_policy import (
    MeasurementType,
    MeasurementValues,
    calculate_amount,
    calculate_measurement,
    calculate_totals,
    decimal_from_text,
    round_quantity,
    signed_measurement_result,
)


def test_synthetic_volume_addition_deduction_and_amount() -> None:
    addition = signed_measurement_result(
        MeasurementType.VOLUME,
        MeasurementValues(Decimal("1"), Decimal("4"), Decimal("2"), Decimal("1.5"), Decimal("0.5")),
        False,
    )
    deduction = signed_measurement_result(
        MeasurementType.VOLUME,
        MeasurementValues(Decimal("1"), Decimal("2"), Decimal("0.5"), Decimal("0.5"), Decimal("0.5")),
        True,
    )
    totals = calculate_totals([addition, deduction])

    assert totals.gross_additions == Decimal("6.0")
    assert totals.gross_deductions == Decimal("0.25")
    assert totals.displayed_quantity == Decimal("5.750")
    assert calculate_amount(totals.displayed_quantity, Decimal("100.00")) == Decimal("575.00")


@pytest.mark.parametrize(
    ("measurement_type", "values", "expected"),
    [
        (MeasurementType.AREA, MeasurementValues(Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")), Decimal("120")),
        (MeasurementType.LENGTH, MeasurementValues(Decimal("2"), Decimal("3"), Decimal("4")), Decimal("24")),
        (MeasurementType.COUNT, MeasurementValues(Decimal("2"), Decimal("3")), Decimal("6")),
        (MeasurementType.DIRECT, MeasurementValues(direct_quantity=Decimal("7.25")), Decimal("7.25")),
    ],
)
def test_measurement_modes_ignore_inactive_dimensions(measurement_type, values, expected) -> None:
    assert calculate_measurement(measurement_type, values).quantity == expected


def test_rounding_uses_half_up_and_amount_uses_displayed_quantity() -> None:
    assert round_quantity(Decimal("1.2345")) == Decimal("1.235")
    assert round_quantity(Decimal("1.2344")) == Decimal("1.234")
    assert calculate_amount(Decimal("1.2345"), Decimal("100")) == Decimal("123.50")


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "not-a-number"])
def test_negative_and_non_finite_values_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        decimal_from_text(value, "Test value")


def test_excessive_deduction_flags_negative_net() -> None:
    result = signed_measurement_result(
        MeasurementType.COUNT,
        MeasurementValues(Decimal("3"), Decimal("1")),
        True,
    )
    totals = calculate_totals([result])
    assert totals.has_negative_net
