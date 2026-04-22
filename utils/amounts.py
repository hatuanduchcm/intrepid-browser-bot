from typing import Optional

import re
import logging

logger = logging.getLogger(__name__)

# Ventures where đ/฿ OCR misread heuristic applies (no explicit currency prefix in output)
_HEURISTIC_VENTURES = {'VN', 'TH'}

# Ventures where '.' is the decimal separator (store as peso.cents, not integer centavos)
_DECIMAL_VENTURES = {'PH'}

# Known multi-character currency prefixes (longest first, case-sensitive)
_MULTI_PREFIXES = ('RM', 'Rp', 'S$')


def clean_amount(amount: Optional[str], venture: str = '') -> Optional[str]:
    """Strip currency prefix and thousand separators from an OCR-extracted amount.

    Mode 1 — explicit prefix found (RM/Rp/S$/đ/d/…):
      Strip it, keep ALL remaining digits as-is.

    Mode 1b — decimal venture (PH): '.' is decimal separator.
      Strip prefix, keep digits + single decimal point.

    Mode 2 — no prefix AND venture in VN/TH:
      Apply OCR-misread heuristic: drop leading '4' or '9' when format
      suggests it was misread from đ/฿ (≥2 digits before first sep, or multi-million).
      Genuine amounts like '40.000' are NOT dropped (only 1 digit before sep).

    Negative sign is always preserved.
    """
    try:
        if amount is None:
            return None

        raw = str(amount).strip()

        # detach leading sign
        sign = ''
        if raw.startswith('-'):
            sign = '-'
            raw = raw[1:].lstrip()

        # --- Mode 1: explicit currency prefix ---
        has_prefix = False

        for prefix in _MULTI_PREFIXES:
            if raw.startswith(prefix):
                raw = raw[len(prefix):].lstrip()
                has_prefix = True
                break

        if not has_prefix and raw and not raw[0].isdigit():
            raw = raw[1:].lstrip()
            has_prefix = True

        digits_and_sep = re.sub(r'[^\d\.,]', '', raw)
        digits = digits_and_sep.replace('.', '').replace(',', '')

        if not digits:
            return sign + digits

        # --- Mode 1b: decimal venture (PH) — '.' is decimal separator, preserve it ---
        if venture.upper() in _DECIMAL_VENTURES:
            # strip thousand separators (commas), keep decimal point
            decimal_str = digits_and_sep.replace(',', '')
            return sign + decimal_str if decimal_str else sign + digits

        if has_prefix:
            return sign + digits

        # --- Mode 2: no prefix — OCR misread heuristic (VN/TH only) ---
        # With vie+eng, đ is read as đ/d (mode 1). If mode 2 triggers, the first
        # digit IS a misread of đ — drop it regardless of which digit it is.
        # Format guards prevent dropping from genuine short amounts like '40.000':
        #   - Sub-million (≥2 digits before first sep): drop any leading digit
        #     e.g. '1499.000' → first_sep=3 → drop → '499000'
        #     e.g. '40.000'   → first_sep=1 → skip → '40000'
        #   - Multi-million (1 digit before first sep, ≥2 seps): drop any leading digit
        #     e.g. '41.452.884' → first_sep=1, sep_count=2 → drop → '1452884'
        if venture.upper() in _HEURISTIC_VENTURES and digits_and_sep:
            rest = digits_and_sep[1:]
            first_sep = next((i for i, c in enumerate(rest) if c in '.,'), len(rest))
            sep_count = rest.count('.') + rest.count(',')
            if first_sep >= 2 or (first_sep == 1 and sep_count >= 2):
                digits = digits[1:]

        return sign + digits
    except Exception:
        logger.exception('clean_amount failed for input: %r', amount)
        return amount

