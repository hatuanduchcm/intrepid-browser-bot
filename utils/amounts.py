from typing import Optional

import re
import logging

logger = logging.getLogger(__name__)

def clean_amount(amount: Optional[str]) -> Optional[str]:
    """Remove separators, detach leading '-', drop the first character of the remaining
    digits (if any), then reapply the '-' if it existed.

    Examples:
      '53.000' -> '3000'
      '4143.300' -> '143300'
      '$116.926' -> '16926'
      '-11.234' -> '-1234'
    """
    try:
        if amount is None:
            return None

        raw = str(amount).strip()

        # detect and detach leading sign
        sign = ''
        if raw.startswith('-'):
            sign = '-'
            raw = raw[1:].lstrip()

        # detect leading non-digit character (treat as the single char to remove)
        currency_first = False
        if raw and not raw[0].isdigit():
            currency_first = True
            # remove that leading non-digit character from the raw string
            raw = raw[1:].lstrip()

        # keep digits and separators only from the remaining text
        digits_and_sep = re.sub(r"[^\d\.,]", "", raw)

        # remove thousand separators and commas
        digits = digits_and_sep.replace('.', '').replace(',', '')

        if not digits:
            return sign + digits

        # If the original first non-space char was a non-digit (currency etc.),
        # we've already consumed that as the "one char to remove" — so keep all remaining digits.
        # Otherwise: drop the first character of the digit string.
        if not currency_first:
            digits = digits[1:] if len(digits) > 0 else ''

        return sign + digits
    except Exception:
        logger.exception('drop_first_after_cleanup failed for input: %r', amount)
        return amount

