import pytest
from order.events.handler_copy_adjustment import parse_lines_to_map
from gsheets.order_adjustment_sheet import ColumnName

@pytest.mark.parametrize("venture, lines, expected", [
    # PH: decimal, prefix, dot
    ("PH", [
        "Service Fee P'53.00",
        "Reverse Shipping Fee -₱-440.00",
        "Total Adjustment Amount P53.00"
    ], {
        ColumnName.SERVICE_FEE: '53.00',
        ColumnName.REVERSE_SHIPPING_FEE: '-440.00',
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '53.00',
    }),
    # VN: remove first digit if no prefix
    ("VN", [
        "Service Fee 4123",
        "Total Adjustment Amount 4123"
    ], {
        ColumnName.SERVICE_FEE: '123',
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '123',
    }),
    # TH: only remove first digit if format matches
    ("TH", [
        "Service Fee ฿4123",
        "Total Adjustment Amount ฿4123"
    ], {
        ColumnName.SERVICE_FEE: '4123',
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '4123',
    }),
    # MY: multi-char prefix
    ("MY", [
        "Service Fee RM75.65",
        "Total Adjustment Amount RM75.65"
    ], {
        ColumnName.SERVICE_FEE: '75.65',
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '75.65',
    }),
    # OCR edge: Bt, dO, etc.
    ("TH", [
        "Service Fee Bt",
        "Total Adjustment Amount dO"
    ], {
        ColumnName.SERVICE_FEE: '1',
        ColumnName.TOTAL_ADJUSTMENT_AMOUNT: '9',
    }),
])
def test_parse_lines_to_map(venture, lines, expected):
    text = "\n".join(lines)
    result = parse_lines_to_map(text, venture=venture)
    for k, v in expected.items():
        val = result.get(k)
        # If val is a list (candidates), check if expected in list
        if isinstance(val, list):
            if v not in val:
                print(f"[DEBUG] venture={venture} result={result}")
            assert v in val
        else:
            if val != v:
                print(f"[DEBUG] venture={venture} result={result}")
            assert val == v
