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

        # --- PH-specific: mạnh tay chuẩn hóa số bị tách, ký tự lạ ---
        if venture.upper() == 'PH' and raw:
            import re as _re
            # Loại bỏ các ký tự lạ sau P/₱ (dấu nháy, ký tự unicode, ký tự không phải số, dấu, hoặc tiền tệ)
            raw = _re.sub(r"([P₱])[\'\u2018\u2019\u02bc\u0060\u00b4\u2032\u2035]+", r"\1", raw)
            # PH-specific: robustly strip Peso prefix with stray apostrophe/quote (trước khi xử lý số)
            peso_prefix = _re.compile(r"^P[\'\u2018\u2019\u02bc\u0060\u00b4\u2032\u2035]?")
            m_prefix = peso_prefix.match(raw)
            if m_prefix:
                raw = raw[m_prefix.end():].lstrip()
            # Chỉ giữ lại số, dấu chấm, phẩy, trừ, và ký hiệu tiền tệ, loại bỏ ký tự lạ khác
            raw = _re.sub(r"[^\d.,\-]", "", raw)
            # Thay mọi dấu '/' thành '7' nếu nằm giữa số
            raw = _re.sub(r'(?<=\d)/(\d)', r'7\1', raw)
            # Thay mọi dấu ',' thành '7' nếu nằm giữa số
            raw = _re.sub(r'(?<=\d),(\d)', r'7\1', raw)
            # Các ký tự dễ nhầm với 1 (l, I, |) vẫn thay thành '1' như cũ
            raw = _re.sub(r'(\d)[lI|](?=[.,]\d{2})', r'\g<1>1', raw)
            raw = raw.replace(' ', '')
            # Nếu không có dấu phẩy thì nối 2 nhóm cuối trước dấu thập phân nếu có nhiều nhóm
            if ',' not in raw:
                m2 = re.match(r'(-?)(\d+)[.,](\d{2})$', raw)
                if m2:
                    sign = m2.group(1)
                    int_part = m2.group(2)
                    dec_part = m2.group(3)
                    # Nếu phần nguyên có 4 số, lấy 2 số cuối; >4 số thì lấy 3 số cuối; <=3 số giữ nguyên
                    if len(int_part) == 4:
                        int_part = int_part[1:]
                    elif len(int_part) > 4:
                        int_part = int_part[-3:]
                    raw = sign + int_part + '.' + dec_part

        # detach leading sign
        sign = ''
        if raw.startswith('-'):
            sign = '-'
            raw = raw[1:].lstrip()

        # --- Mode 1: explicit currency prefix ---
        has_prefix = False


        # --- PH-specific: robustly strip Peso prefix with stray apostrophe/quote ---
        if venture.upper() == 'PH':
            # Remove P', P’, P`, P´, P′, P‵, etc. as prefix
            import re as _re
            peso_prefix = _re.compile(r"^P[\'\u2018\u2019\u02bc\u0060\u00b4\u2032\u2035]?")
            m = peso_prefix.match(raw)
            if m:
                raw = raw[m.end():].lstrip()
                has_prefix = True

        if not has_prefix:
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

