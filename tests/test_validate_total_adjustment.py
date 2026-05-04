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


def test_validate_total_adjustment_th_refund_amount_412206000():
    # TH scenario: RefundAmount 412206000, Reverse Shipping Fee -440.000, PiShip Program Savings d40.000,
    # Commission Fee 6355.166, Service Fee 470.179, Transaction Fee 4108.315, Total Adjustment Amount -91.672.340


    parsed = {
        ColumnName.REFUND_AMOUNT: ['2206000'],
        ColumnName.REVERSE_SHIPPING_FEE: ['-440000', '-40000', '-0000'],
        ColumnName.PISHIP_PROGRAM_SAVINGS: ['40000', '0000', '000'],
        ColumnName.COMMISSION_FEE: ['355166', '55166'],
        ColumnName.SERVICE_FEE: ['70179', '0179'],
        ColumnName.TRANSACTION_FEE: ['108315', '08315'],
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: ['-1672340', '-672340'],
        '__venture__': 'VN',
    }

    result = validate_total_adjustment_with_negatives(parsed)

    assert result is not None
    assert result['matches'] is True
    assert result['expected_sum'] == -1672340
    assert result['total_value'] == -1672340


def test_validate_total_adjustment_vn_refund_amount_ocr_candidates():
    # VN scenario, mapping dạng list giống ảnh OCR parse đầu vào
    parsed = {
        ColumnName.REFUND_AMOUNT: ['412206000', '12206000', '2206000'],
        ColumnName.REVERSE_SHIPPING_FEE: ['-440000', '-40000', '-0000'],
        ColumnName.PISHIP_PROGRAM_SAVINGS: ['40000', '0000', '000'],
        ColumnName.COMMISSION_FEE: ['355166', '55166'],
        ColumnName.SERVICE_FEE: ['70179', '0179'],
        ColumnName.TRANSACTION_FEE: ['108315', '08315'],
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: ['-1672340', '-672340'],
        '__venture__': 'VN',
    }

    result = validate_total_adjustment_with_negatives(parsed)

    assert result is not None
    assert result['matches'] is True
    assert result['expected_sum'] == -1672340
    assert result['total_value'] == -1672340


def test_add_negative_candidates_refund_amount():
    def test_validate_total_adjustment_vn_refund_amount_exact_combo():
        # Test với đúng tổ hợp thực tế như UI, không cần thử nhiều tổ hợp
        parsed = {
            ColumnName.REFUND_AMOUNT: '-2206000',
            ColumnName.REVERSE_SHIPPING_FEE: '-440000',
            ColumnName.PISHIP_PROGRAM_SAVINGS: '40000',
            ColumnName.COMMISSION_FEE: '355166',
            ColumnName.SERVICE_FEE: '70179',
            ColumnName.TRANSACTION_FEE: '108315',
            ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '-1672340',
            '__venture__': 'VN',
        }

        result = validate_total_adjustment_with_negatives(parsed)

        assert result is not None
        assert result['matches'] is True
        assert result['expected_sum'] == -1672340
        assert result['total_value'] == -1672340
    from utils.amounts import add_negative_candidates
    candidates = ['412206000', '12206000', '2206000']
    result = add_negative_candidates(candidates)
    # Kết quả mong đợi: thêm số âm cho từng số dương
    expected = ['412206000', '12206000', '2206000', '-412206000', '-12206000', '-2206000']
    assert set(result) == set(expected)
