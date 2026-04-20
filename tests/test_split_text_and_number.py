import pytest

from order.events.handler_copy_adjustment import split_text_and_number


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
        
    ]

    for line, (exp_label, exp_num) in cases:
        label, num = split_text_and_number(line)
        assert label == exp_label
        assert num == exp_num
