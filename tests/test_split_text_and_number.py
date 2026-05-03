# No direct usage of clean_amount in this file, so no changes needed
import pytest
from utils.split_text_and_number import split_text_and_number, try_ocr_currency_token


def test_split_text_and_number_various():
    cases = [
        ("Service Fee ¢53.000", ("service fee", "¢53.000")),
        ("Service Fee $116.926", ("service fee", "$116.926")),
        ("Subtotal Shipping Fee Charged by 4143.300", ("subtotal shipping fee charged by", "4143.300")),
        (f"Service Fee {chr(0xfffd)}53.000", ("service fee", chr(0xfffd) + "53.000")),
        ("Reverse Shipping Fee -440.000", ("reverse shipping fee", "-440.000")),
        ("Service Fee $53.000", ("service fee", "$53.000")),
        ("Service Fee d7.520", ("service fee", "d7.520")),
        ("Service Fee 41.000", ("service fee", "41.000")),
        ("Voucher Sponsored by Seller d41.000", ("voucher sponsored by seller", "d41.000")),
        ("ce Subtotal Shipping Fee Charged by Logistic | 432.200", ("ce subtotal shipping fee charged by logistic", "432.200")),
        ("Transaction Fee d9 329", ("transaction fee", "d9329")),
        ("Compensation as Parcel was Lost P3,/21.31", ("compensation as parcel was lost", "P3,721.31")),
        ("Total Adjustment Amount -P'2,042.96", ("total adjustment amount", "-P2,042.96")),
        ("Service Fee P11 22.00", ("service fee", "P1122.00")),
        ("Service Fee d4 686", ("service fee", "d4686")),
        ("Service Fee Bt", ("service fee", "b1")),
        ("Total Adjustment Amount d118./12", ("total adjustment amount", "d118.712")),
        ("Total Adjustment Amount g905 . 000", ("total adjustment amount", "g905.000")),
        
    ]

    for line, (exp_label, exp_num) in cases:
        label, num = split_text_and_number(line)
        assert label == exp_label
        assert num == exp_num


def test_try_ocr_currency_token():
    cases = [
        ("Bt", "B1"),
        ("dO", "d9"),
        ("dS", "d5"),
        ("-Bt", "-B1"),
        ("₱O", "₱9"),
        ("$O", "$9"),
        ("d9.000", "d9.000"),
        ("B8so", "B850"),
        ("-₱-53.00", "-₱53.00"),
        ("P°53.00", "P53.00"),
        ("P'53.00", "P53.00"),
        ("P‘53.00", "P53.00"),
        ("P’53.00", "P53.00"),
        ("P`53.00", "P53.00"),
        ("P´53.00", "P53.00"),
        ("#53.00", "P53.00"),
        ("d118./12", "d118.712"),

    ]
    for inp, expected in cases:
        assert try_ocr_currency_token(inp) == expected
