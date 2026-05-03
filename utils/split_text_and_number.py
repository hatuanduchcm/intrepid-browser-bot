import re as _re

# Currency prefixes that OCR often renders as a single letter
_CURRENCY_LETTER_PREFIXES = _re.compile(r'^[-+]?\s*[฿₱B$€£¥₫đdPRr]\s*', _re.IGNORECASE)

# OCR misread normalization: (pattern, replacement) applied before number extraction.
# Handles Philippine Peso ₱ being read as 'P°', '#', etc.
_OCR_CURRENCY_NORMALIZE = [
    (_re.compile(r'P°', _re.IGNORECASE), '₱'),                   # P° → ₱
    (_re.compile(r"P['\u2018\u2019\u02bc\u0060\u00b4]"), '₱'),   # P' P' P` P´ → ₱
    (_re.compile(r'(?<![\w])#(?=\d)'), '₱'),                     # # before digit → ₱
    (_re.compile(r'(?<!\w)P(?=[-\d])'), '₱'),                    # bare P before digit/minus → ₱ (e.g. P35.00, P-57.00)
    (_re.compile(r'[-+]?₱-(?=\d)'), lambda m: '-₱'),             # collapse double-sign: -₱- or ₱- → -₱
    # Bold-text OCR: '/' misread as '7' immediately after currency prefix
    # e.g. "Rp/7.000" → "Rp77.000", "Rp/77.000" → "Rp777.000"
    (_re.compile(r'(Rp|RM|R\\$)\s*/\s*(?=\d)', _re.IGNORECASE), lambda m: m.group(1) + '7'),
]

def try_ocr_currency_token(token: str):
    """If `token` looks like a currency letter + OCR-confused digits (e.g. 'Bt'),
    return the corrected numeric string (e.g. 'B1'), else return None.

    Preserves the leading currency letter so clean_amount can strip it.
    """
    t = token.strip()
    # Normalize OCR currency (P°, P', #, ...)
    for pat, rep in _OCR_CURRENCY_NORMALIZE:
        t = pat.sub(rep, t)
    # Collapse double sign: -₱-53.00 -> -₱53.00
    t = _re.sub(r'^(-₱)-', r'\1', t)
    sign = ''
    if t.startswith('-'):
        sign = '-'
        t = t[1:].lstrip()
    # Must start with a known currency-like letter
    m = _CURRENCY_LETTER_PREFIXES.match(t)
    if not m:
        return None
    currency_part = m.group(0)
    rest = t[m.end():]
    # Handle OCR confusion of '/' as '7' in bold text (e.g. "Rp/7.000" → "Rp77.000")
    rest = _re.sub(r'/', '7', rest)

    if not rest:
        return None
    # Heuristic: if rest has NO real digit, letters like O/o are misreads of 9 (not 0).
    # Rationale: OCR correctly outputs the digit '0' when it sees a zero; the LETTER 'O'
    # in numeric position means OCR confused the shape of '9' with 'O'.
    # When real digits exist alongside letters (e.g. '8so'), O→0 is still correct.
    if not _re.search(r'\d', rest):
        _token_map = str.maketrans({'O': '9', 'o': '9', 'S': '5', 's': '5',
                                    't': '1', 'T': '1', 'l': '1', 'I': '1',
                                    'Z': '2', 'z': '2', 'G': '6', 'g': '9', 'B': '8'})
    else:
        _token_map = _OCR_LETTER_TO_DIGIT
    corrected = rest.translate(_token_map)
    # Chỉ kiểm tra phần số sau prefix là hợp lệ (cho phép prefix currency)
    if _re.fullmatch(r'[\d\.,]+', corrected):
        return sign + currency_part + corrected
    # Nếu toàn bộ kết quả là prefix + số/chấm/phẩy, cũng chấp nhận
    if _re.fullmatch(r'[a-zA-Z₫đ₱฿$]+[\d\.,]+', sign + currency_part + corrected):
        return sign + currency_part + corrected
    return None

_OCR_LETTER_TO_DIGIT = str.maketrans({
    't': '1', 'T': '1',
    'l': '1', 'I': '1',
    'O': '0', 'o': '0',
    'S': '5', 's': '5',
    'Z': '2', 'z': '2',
    'G': '6', 'g': '9',
    'B': '8',
})

_OCR_CURRENCY_NORMALIZE = [
    (_re.compile(r'P°', _re.IGNORECASE), 'P'),
    (_re.compile(r"P['\u2018\u2019\u02bc\u0060\u00b4]"), 'P'),
    (_re.compile(r'(?<![\w])#(?=\d)'), 'P'),
]

def split_text_and_number(line: str):
    if not line:
        return "", ""

    # --- normalize OCR currency
    for pat, rep in _OCR_CURRENCY_NORMALIZE:
        line = pat.sub(rep, line)

    line = line.replace('|', ' ')

    # --- STEP 1: tìm số cuối cùng (anchor chắc chắn)
    m = _re.search(r'[-+]?\d[\d,./\s]*$', line)
    if not m:
        label = line.strip().lower()
        num = ""
        # Nếu không tách được số, thử kiểm tra token cuối cùng của label
        tokens = label.split()
        if tokens:
            maybe_num = tokens[-1]
            fixed = try_ocr_currency_token(maybe_num)
            if fixed is not None:
                num = fixed
                label = ' '.join(tokens[:-1])
        return label, num

    start = m.start()
    end = m.end()

    # --- STEP 2: mở rộng ngược để lấy prefix (P, d, $, ¢, P', etc.)
    i = start - 1
    while i >= 0 and line[i] not in " \t":
        i -= 1

    label = line[:i+1].strip().lower()
    num = line[i+1:end].strip()

    # --- normalize
    num = _re.sub(r"\s+", "", num)

    # --- try to fix OCR currency token if needed
    fixed = try_ocr_currency_token(num)
    if fixed is not None:
        num = fixed

    return label, num