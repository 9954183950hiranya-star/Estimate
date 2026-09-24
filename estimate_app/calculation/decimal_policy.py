from decimal import ROUND_HALF_UP, Decimal


MONEY_PLACES = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    """Round monetary values to two decimal places using half-up rounding."""
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
