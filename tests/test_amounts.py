import pytest

from utils.amounts import clean_amount


def test_clean_amount_explicit_prefix():
    """Explicit currency prefix: strip and keep all digits."""
    # single-char
    assert '116926' in clean_amount('$116.926', venture='VN')
    assert '7520' in clean_amount('d7.520', venture='VN')
    assert '314342' in clean_amount('đ314.342', venture='VN')
    assert '20292' in clean_amount('đ20.292', venture='VN')
    assert '-40000' in clean_amount('-đ40.000', venture='VN')
    assert '-2480600' in clean_amount('-d2.480.600', venture='VN')
    assert '116926' in clean_amount('฿116.926', venture='TH')
    assert '-40000' in clean_amount('-฿40.000', venture='TH')
    # MY: RM prefix (giữ dấu chấm thập phân)
    assert '75.65' in clean_amount('RM75.65', venture='MY')
    assert '-75.65' in clean_amount('-RM75.65', venture='MY')
    assert '9.56' in clean_amount('RM9.56', venture='MY')
    assert '-61.04' in clean_amount('-RM61.04', venture='MY')
    assert '0.34' in clean_amount('RM0.34', venture='MY')
    # ID: Rp prefix
    assert '950000' in clean_amount('Rp950.000', venture='ID')
    assert '-950000' in clean_amount('-Rp950.000', venture='ID')
    assert '94525' in clean_amount('Rp94.525', venture='ID')
    assert '1250' in clean_amount('Rp1.250', venture='ID')
    assert '-756375' in clean_amount('-Rp756.375', venture='ID')


def test_clean_amount_vn_heuristic():
    """VN/TH: đ misread as ANY digit — drop when format matches."""
    # misread as 4
    assert '314342' in clean_amount('4314.342', venture='VN')
    assert '3000' in clean_amount('43.000', venture='VN')
    assert '19600' in clean_amount('419.600', venture='VN')
    # misread as 9
    assert '49218' in clean_amount('949.218', venture='VN')
    assert '15536' in clean_amount('915.536', venture='VN')
    # misread as 1
    assert '499000' in clean_amount('1499.000', venture='VN')
    assert '388400' in clean_amount('1388.400', venture='VN')
    assert '-499000' in clean_amount('-1499.000', venture='VN')
    # misread as 3
    assert '116926' in clean_amount('3116.926', venture='VN')
    assert '89049' in clean_amount('389.049', venture='VN')
    # multi-million (any leading digit)
    assert '1889200' in clean_amount('41.889.200', venture='VN')
    assert '1452884' in clean_amount('41.452.884', venture='VN')
    assert '2480600' in clean_amount('42.480.600', venture='VN')
    assert '1452884' in clean_amount('31.452.884', venture='VN')
    # negative
    assert '-309617' in clean_amount('-4309.617', venture='VN')
    assert '-20700' in clean_amount('-420.700', venture='VN')
    assert '-1889200' in clean_amount('-41.889.200', venture='VN')
    # genuine — 1 digit before sep: NOT dropped
    assert '4000' in clean_amount('44.000', venture='VN')
    assert '-4000' in clean_amount('-44.000', venture='VN')
    assert '-2480600' in clean_amount('-2.480.600', venture='VN')
    assert '1452884' in clean_amount('1.452.884', venture='VN')
    assert '4686' in clean_amount('d4 686', venture='VN')
    assert '4686' in clean_amount('d4686', venture='VN')


def test_clean_amount_no_venture_no_heuristic():
    """Without venture, no OCR heuristic — plain number preserved."""
    # assert clean_amount('314.342') == '314342'
    # assert clean_amount('40.000') == '40000'
    # assert clean_amount('314.342') == '314342'  # NOT dropped without venture
    # assert clean_amount(None) is None

    # Test clean_amount chỉ trả về các số gốc
    assert set(clean_amount('412206000')) == {'412206000', '12206000', '2206000'}
    assert set(clean_amount('2206000')) == {'2206000', '206000', '06000'}
    assert set(clean_amount('-2206000')) == {'-2206000', '-206000', '-06000'}

    # Test add_negative_candidates sinh thêm số âm
    from utils.amounts import add_negative_candidates
    assert set(add_negative_candidates(clean_amount('412206000'))) == {'412206000', '12206000', '2206000', '-412206000', '-12206000', '-2206000'}
    assert set(add_negative_candidates(clean_amount('2206000'))) == {'2206000', '-2206000', '206000', '-206000', '06000', '-06000'}
    assert set(add_negative_candidates(clean_amount('-2206000'))) == {'-2206000', '-206000', '-06000'}
