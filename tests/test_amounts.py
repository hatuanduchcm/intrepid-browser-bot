import pytest

from utils.amounts import clean_amount


def test_drop_first_after_cleanup():
    # remove separators, detach '-', drop first char, reapply sign
    assert clean_amount('�53.000') == '53000'
    assert clean_amount('¢53.000') == '53000'
    assert clean_amount('$53.000') == '53000'
    assert clean_amount('4143.300') == '143300'
    assert clean_amount('$116.926') == '116926'
    assert clean_amount('-11.234') == '-1234'
    assert clean_amount('d7.520') == '7520'
    assert clean_amount(None) is None
