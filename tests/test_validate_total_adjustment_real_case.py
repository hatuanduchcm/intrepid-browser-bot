import pytest
from gsheets.order_adjustment_sheet import ColumnName
from order.events.handler_copy_adjustment import validate_total_adjustment_with_negatives

def test_validate_total_adjustment_real_case_candidate_noise():
    parsed = {
        ColumnName.REFUND_AMOUNT: ['412206000', '12206000', '2206000'],
        ColumnName.REVERSE_SHIPPING_FEE: ['-440000', '-40000', '-0000'],
        ColumnName.PISHIP_PROGRAM_SAVINGS: ['40000', '0000', '000'],
        ColumnName.COMMISSION_FEE: ['6355166', '355166', '55166'],
        ColumnName.SERVICE_FEE: ['470179', '70179', '0179'],
        ColumnName.TRANSACTION_FEE: ['4108315', '108315', '08315'],
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: ['-91672340', '-1672340', '-672340'],
        '__venture__': 'VN',
    }
    result = validate_total_adjustment_with_negatives(parsed)
    print('Result:', result)
    assert result is not None
    assert result['matches'] is True
    assert result['expected_sum'] == -1672340
    assert result['total_value'] == -1672340
