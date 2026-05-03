import pytest

from gsheets.order_adjustment_sheet import ColumnName
from order.events.handler_copy_adjustment import validate_total_adjustment, validate_total_adjustment_with_negatives


def test_validate_total_adjustment_match_enum_key():
    parsed = {
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '53.000',
        ColumnName.SERVICE_FEE: '30.000',
        ColumnName.TRANSACTION_FEE: '23.000',
    }

    result = validate_total_adjustment_with_negatives(parsed)

    assert result is not None
    assert result['matches'] is True
    assert result['expected_sum'] == 53000
    assert result['total_value'] == 53000


def test_validate_total_adjustment_mismatch_enum_key():
    parsed = {
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '60.000',
        ColumnName.SERVICE_FEE: '30.000',
        ColumnName.TRANSACTION_FEE: '23.000',
    }

    result = validate_total_adjustment_with_negatives(parsed)

    assert result is not None
    assert result['matches'] is False
    assert result['expected_sum'] == 60000
    assert result['total_value'] == 53000


def test_validate_total_adjustment_missing_key_returns_none():
    parsed = {
        ColumnName.SERVICE_FEE: '10.000',
        ColumnName.TRANSACTION_FEE: '5.000',
    }

    assert validate_total_adjustment_with_negatives(parsed) is None


def test_validate_total_adjustment_string_key_returns_none():
    # Current implementation expects enum key; string-key fallback is not active
    parsed = {
        str(ColumnName.TOTAL_ADJUSTMENT_AMOUNT): '10.000',
        ColumnName.SERVICE_FEE: '5.000',
    }

    assert validate_total_adjustment_with_negatives(parsed) is None
