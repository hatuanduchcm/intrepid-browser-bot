def add_negative_candidates(result):
    """
    Nhận vào list kết quả (candidates), trả về list đã thêm số âm cho các số dương chưa có số âm tương ứng.
    Không làm thay đổi thứ tự các số dương gốc, số âm thêm vào ở cuối.
    """
    def is_number(s):
        try:
            float(s.replace(',', ''))
            return True
        except Exception:
            return False
    out = list(result)
    for c in result:
        if is_number(c) and not c.startswith('-') and ('-' + c) not in out:
            out.append('-' + c)
    return out
from typing import Optional

import re
import logging

logger = logging.getLogger(__name__)

# Ventures where đ/฿ OCR misread heuristic applies (no explicit currency prefix in output)
_HEURISTIC_VENTURES = {'VN', 'TH'}

# Ventures where '.' is the decimal separator (store as peso.cents, not integer centavos)
_DECIMAL_VENTURES = {'PH', 'MY'}

# Known multi-character currency prefixes (longest first, case-sensitive)
_MULTI_PREFIXES = ('RM', 'Rp', 'S$')


from typing import List

def clean_amount(amount: Optional[str], venture: str = '') -> List[str]:
    """Return a list of plausible cleaned numbers from an OCR-extracted amount."""
    candidates = []
    try:
        if amount is None:
            logger.debug(f"[clean_amount] input is None, returning ['']")
            return ['']

        raw = str(amount).strip()

        # --- PH-specific: chỉ loại bỏ dấu phẩy, giữ dấu chấm, giữ nguyên phần nguyên ---
        if venture.upper() == 'PH' and raw:
            import re as _re2
            m_force = _re2.match(r'^P?([\d,\./]+)[.,](\d{2})$', raw)
            if m_force:
                int_part_raw = m_force.group(1)
                dec_part = m_force.group(2)
                # Only replace '/' with '7' (OCR misread), NOT commas (thousand separators)
                int_part = _re2.sub(r'\/', '7', int_part_raw)
                int_part = _re2.sub(r'[^\d]', '', int_part)
                if int_part:
                    int_part_fmt = f"{int(int_part):,}"
                    val = int_part_fmt + '.' + dec_part
                    candidates.append(val)
                    return candidates
            import re as _re
            raw = _re.sub(r"([P₱])[\'\u2018\u2019\u02bc\u0060\u00b4\u2032\u2035]+", r"\1", raw)
            peso_prefix = _re.compile(r"^P[\'\u2018\u2019\u02bc\u0060\u00b4\u2032\u2035]?")
            m_prefix = peso_prefix.match(raw)
            if m_prefix:
                raw = raw[m_prefix.end():].lstrip()
            raw = _re.sub(r"[^\d.,\-]", "", raw)
            raw = _re.sub(r'(?<=\d)/(\d)', r'7\1', raw)
            raw = _re.sub(r'(\d)[lI|](?=[.,]\d{2})', r'\g<1>1', raw)
            raw = raw.replace(' ', '')
            if re.match(r"^-?\d{1,3}(,\d{3})+[.,]\d{2}$", raw):
                raw = raw.replace(',', '')
                candidates.append(raw)
                return candidates
            raw = re.sub(r'(?<=\d)[/,](?=\d)', '7', raw)
            m = re.match(r'(-?)(\d+)[.,](\d{2})$', raw)
            if m:
                sign = m.group(1)
                int_part = m.group(2)
                dec_part = m.group(3)
                if len(int_part) > 3:
                    int_part_fmt = f"{int(int_part):,}"
                else:
                    int_part_fmt = int_part
                val = sign + int_part_fmt + '.' + dec_part
                candidates.append(val)
                return candidates
            candidates.append(raw)
            return candidates

        sign = ''
        if raw.startswith('-'):
            sign = '-'
            raw = raw[1:].lstrip()

        PREFIXES = (
            'RM', 'Rp', 'S$',
            '₱', 'P', '$', '฿', 'đ', 'd', '₫'
        )
        if raw:
            raw = re.sub(r"^([P₱])[\'\u2018\u2019\u02bc\u0060\u00b4\u2032\u2035]+", r"\1", raw)
        while raw:
            matched = False
            for prefix in PREFIXES:
                if raw.startswith(prefix):
                    raw = raw[len(prefix):].lstrip()
                    matched = True
                    break
            if not matched:
                break
        has_prefix = True if raw != str(amount).strip().lstrip('-') else False

        digits_and_sep = re.sub(r'[^\d\.,]', '', raw)
        digits = digits_and_sep.replace('.', '').replace(',', '')

        if not digits:
            logger.debug(f"[clean_amount] No digits after prefix removal, returning ['']")
            return ['']

        # --- Mode 1b: decimal venture (PH) — '.' is decimal separator, preserve it ---
        if venture.upper() in _DECIMAL_VENTURES:
            decimal_str = digits_and_sep.replace(',', '')
            val = sign + decimal_str if decimal_str else sign + digits
            candidates.append(val)
        else:
            val = sign + digits
            candidates.append(val)

        # --- Generate candidates by removing 1 or 2 leading digits if plausible ---
        for n in range(1, min(3, len(digits))):
            # Only consider if after removing n digits, still at least 2 digits left
            if len(digits) - n >= 2:
                cand = sign + digits[n:]
                if cand not in candidates:
                    candidates.append(cand)

        # For decimal ventures, also try removing 1 or 2 leading digits from decimal_str
        if venture.upper() in _DECIMAL_VENTURES and len(digits_and_sep) > 2:
            for n in range(1, min(3, len(digits_and_sep))):
                cand = sign + digits_and_sep[n:].replace(',', '')
                if cand not in candidates and len(cand.replace('.', '')) >= 2:
                    candidates.append(cand)

        # Remove duplicates, preserve order
        seen = set()
        result = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result
    except Exception as e:
        logger.exception('clean_amount failed for input: %r, error: %s', amount, e)
        try:
            raw = str(amount).strip() if amount is not None else ''
            sign = '-' if raw.startswith('-') else ''
            raw = raw[1:].lstrip() if sign else raw
            digits_and_sep = re.sub(r'[^\d\.,]', '', raw)
            digits = digits_and_sep.replace('.', '').replace(',', '')
            candidates = [sign + digits] if digits else ['']
            return candidates
        except Exception:
            return ['']

