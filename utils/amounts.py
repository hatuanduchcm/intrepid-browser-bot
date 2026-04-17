from typing import Optional


def trim_leading_integer_digits(amount: Optional[str], keep_last_n: int = 3) -> Optional[str]:
    """Trim leading digits of the integer part so only the last `keep_last_n` digits remain.

    Examples: '-4269.500' -> '-269.500' when keep_last_n=3.
    If no decimal part, preserve sign.
    """
    if not amount:
        return amount
    s = amount.strip()
    sign = ''
    if s.startswith('-'):
        sign = '-'
        s = s[1:]
    s = s.replace(',', '')
    parts = s.split('.')
    intp = parts[0] if parts else ''
    frac = parts[1] if len(parts) > 1 else ''
    # Simplified behavior: remove the first digit of the integer part if present
    if len(intp) > 1:
        intp = intp[1:]
    out = sign + intp
    if frac:
        out = out + '.' + frac
    return out


def process_amount_for_region(amount: Optional[str], region: str = '') -> Optional[str]:
    """Apply region-specific normalization to `amount` string.

    Currently: if region indicates Vietnam ('vn' or 'vietnam'), trim leading integer digits to keep last 3.
    """
    if not amount:
        return amount
    if not region:
        return amount
    r = region.strip().lower()
    if r in ('vn', 'vietnam'):
        # normalize common VN formatting: dots often used as thousand separators
        s = amount.strip()
        sign = ''
        if s.startswith('-'):
            sign = '-'
            s = s[1:]
        # if there's a comma used as decimal separator, convert to dot
        if ',' in s and not '.' in s:
            s = s.replace(',', '.')
        # if dot appears and the part after dot has 3 digits, treat as thousand separator and remove dots
        import re
        parts = s.split('.')
        if len(parts) > 1 and all(re.fullmatch(r"\d{3}", p) for p in parts[1:]):
            # remove all dots
            s = s.replace('.', '')
        # reattach sign and apply trimming
        s = sign + s
        return trim_leading_integer_digits(s)
    return amount
