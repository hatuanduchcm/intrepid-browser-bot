from typing import Optional

import re
import logging

logger = logging.getLogger(__name__)

# Ventures where đ/฿ OCR misread heuristic applies (no explicit currency prefix in output)
_HEURISTIC_VENTURES = {'VN', 'TH'}

# Known multi-character currency prefixes (longest first, case-sensitive)
_MULTI_PREFIXES = ('RM', 'Rp', 'S$')


def clean_amount(amount: Optional[str], venture: str = '') -> Optional[str]:
    """Strip currency prefix and thousand separators from an OCR-extracted amount.

    Mode 1 — explicit prefix found (RM/Rp/S$/đ/d/…):
      Strip it, keep ALL remaining digits as-is.

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

        if has_prefix:
            return sign + digits

        # --- Mode 2: no prefix — OCR misread heuristic (VN/TH only) ---
        # đ can be misread as '4', '9', or '1'.
        # Drop the leading digit when:
        #   - Sub-million format (≥2 digits before first sep): applies to '4', '9', '1'
        #     e.g. '1499.000' → first_sep(rest)=3 ≥ 2 → drop → '499000'
        #     e.g. '4314.342' → first_sep(rest)=3 ≥ 2 → drop → '314342'
        #   - Multi-million format (1 digit before first sep, ≥2 seps): only '4' and '9'
        #     e.g. '41.452.884' → drop → '1452884'
        #     '1.452.884' is kept as-is (legitimate value, đ was just dropped by OCR)
        if venture.upper() in _HEURISTIC_VENTURES and digits_and_sep and digits_and_sep[0] in '149':
            leading = digits_and_sep[0]
            rest = digits_and_sep[1:]
            first_sep = next((i for i, c in enumerate(rest) if c in '.,'), len(rest))
            sep_count = rest.count('.') + rest.count(',')
            should_drop = (
                first_sep >= 2  # sub-million: all 3 misread chars
                or (leading in '49' and first_sep == 1 and sep_count >= 2)  # multi-million: only 4/9
            )
            if should_drop:
                digits = digits[1:]

        return sign + digits
    except Exception:
        logger.exception('clean_amount failed for input: %r', amount)
        return amount

