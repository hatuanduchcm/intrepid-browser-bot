import pytest

from utils.amounts import clean_amount


def test_clean_amount_explicit_prefix():
    """Explicit currency prefix: strip and keep all digits."""
    # single-char
    assert clean_amount('$116.926') == '116926'
    assert clean_amount('d7.520') == '7520'
    assert clean_amount('đ314.342') == '314342'
    assert clean_amount('đ20.292') == '20292'
    assert clean_amount('-đ40.000') == '-40000'
    assert clean_amount('-d2.480.600') == '-2480600'
    assert clean_amount('-1499.000') == '-499000'
    assert clean_amount('฿116.926', venture='TH') == '116926'
    assert clean_amount('฿7.520', venture='TH') == '7520'
    assert clean_amount('฿314.342', venture='TH') == '314342'
    assert clean_amount('฿20.292', venture='TH') == '20292'
    assert clean_amount('-฿40.000', venture='TH') == '-40000'
    assert clean_amount('-฿2.480.600', venture='TH') == '-2480600'
    # MY: RM prefix
    assert clean_amount('RM75.65', venture='MY') == '7565'
    assert clean_amount('-RM75.65', venture='MY') == '-7565'
    assert clean_amount('RM9.56', venture='MY') == '956'
    assert clean_amount('-RM61.04', venture='MY') == '-6104'
    assert clean_amount('RM0.34', venture='MY') == '034'
    # ID: Rp prefix
    assert clean_amount('Rp950.000', venture='ID') == '950000'
    assert clean_amount('-Rp950.000', venture='ID') == '-950000'
    assert clean_amount('Rp94.525', venture='ID') == '94525'
    assert clean_amount('Rp1.250', venture='ID') == '1250'
    assert clean_amount('-Rp756.375', venture='ID') == '-756375'


def test_clean_amount_vn_heuristic():
    """VN/TH: OCR misread of đ as '4', '9', or '1' — drop when format matches."""
    # hundreds of thousands (4/9)
    assert clean_amount('4314.342', venture='VN') == '314342'
    assert clean_amount('453.000', venture='VN') == '53000'
    assert clean_amount('949.218', venture='VN') == '49218'
    assert clean_amount('915.536', venture='VN') == '15536'
    assert clean_amount('419.600', venture='VN') == '19600'
    # multi-million (4/9)
    assert clean_amount('41.889.200', venture='VN') == '1889200'
    assert clean_amount('41.452.884', venture='VN') == '1452884'
    assert clean_amount('42.480.600', venture='VN') == '2480600'
    # hundreds of thousands (1 = đ misread)
    assert clean_amount('1499.000', venture='VN') == '499000'
    assert clean_amount('1388.400', venture='VN') == '388400'
    assert clean_amount('-1499.000', venture='VN') == '-499000'
    # '1' NOT dropped for multi-million (legitimate value)
    assert clean_amount('1.452.884', venture='VN') == '1452884'
    # negative
    assert clean_amount('-4309.617', venture='VN') == '-309617'
    assert clean_amount('-420.700', venture='VN') == '-20700'
    assert clean_amount('-41.889.200', venture='VN') == '-1889200'
    # genuine amounts starting with 4/9 — single digit before sep → skip drop
    assert clean_amount('40.000', venture='VN') == '40000'
    assert clean_amount('-40.000', venture='VN') == '-40000'
    assert clean_amount('-2.480.600', venture='VN') == '-2480600'


def test_clean_amount_no_venture_no_heuristic():
    """Without venture, no OCR heuristic — plain number preserved."""
    assert clean_amount('314.342') == '314342'
    assert clean_amount('40.000') == '40000'
    assert clean_amount('4314.342') == '4314342'  # NOT dropped without venture
    assert clean_amount(None) is None
